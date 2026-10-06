from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from ..models import PointVente, PointVenteEntrepot, CaissePointVente
from ..services.pos_service import PointVenteService
from ..services.caisse_session_service import CaisseSessionService, get_session_non_finalisee_caisse
from ..services.access_service import POSAccessService
from ..constants import ActionPOS, ModeAccesPOS
from apps.tresorerie.models import Caisse
from apps.stock.models import Produit, StockEntrepot, Domaine, Entrepot
from apps.restaurant.models import MenuModel
from apps.authentication.groups import PATRON, MANAGER, BAR, RESTAURANT, CAISSIER, RAF
from apps.pos.models import AffectationPointVente, ShiftEmploye
from apps.entreprises.models import Entreprise

def _get_planning_actif(employe, point_vente):
    if not employe or not point_vente:
        return None
    decision = POSAccessService.check(
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.ACCEDER,
    )
    if not decision.allowed or not decision.shift_id:
        return None
    return ShiftEmploye.objects.filter(pk=decision.shift_id).first()


RAF_MODES = [
    ('brasserie', 'Brasserie', '\U0001f37a'),
    ('restaurant', 'Restaurant', '\U0001f37d'),
    ('location', 'R\u00e9servation', '\U0001f3e8'),
]


def get_employe_pv_ids(employe):
    if not employe or not getattr(employe, "user", None):
        return []
    return list(
        POSAccessService.points_accessibles(user=employe.user)
        .values_list("id", flat=True)
    )


GROUPES_VUE_GLOBALE = [PATRON, MANAGER, RAF]


def a_vue_globale_commandes(user):
    return user.groups.filter(name__in=GROUPES_VUE_GLOBALE).exists()


def get_pv_courant_id(request):
    # Ne jamais faire confiance aveuglément au PV stocké en session : un horaire
    # ou un shift peut avoir expiré. Exception contrôlée : le propriétaire d'une
    # session financière non finalisée garde ce PV comme contexte de finalisation.
    pv_id = request.session.get('point_vente_courant_id')
    if pv_id:
        point = PointVente.objects.filter(pk=pv_id, actif=True).first()
        if point and POSAccessService.can(
            user=request.user,
            point_vente=point,
            action=ActionPOS.ACCEDER,
        ):
            return point.id

        employe = getattr(request.user, 'employe', None)
        if point and employe:
            cpv = (
                CaissePointVente.objects
                .filter(point_vente=point, actif=True)
                .select_related('caisse')
                .order_by('-principale', 'id')
                .first()
            )
            session = (
                get_session_non_finalisee_caisse(cpv.caisse)
                if cpv else None
            )
            if session and session.ouverte_par_id == employe.id:
                can_finalize, _ = (
                    CaisseSessionService.autoriser_finalisation_session(
                        session,
                        employe,
                    )
                )
                if can_finalize:
                    return point.id

        request.session.pop('point_vente_courant_id', None)

    point = POSAccessService.points_accessibles(
        user=request.user,
        action=ActionPOS.ACCEDER,
    ).first()
    return point.id if point else None


def a_planning_aujourdhui(employe, point_vente):
    if not employe or not point_vente:
        return False
    aujourdhui = timezone.localtime().date()
    return ShiftEmploye.objects.filter(
        affectation__employe=employe,
        affectation__point_vente=point_vente,
        debut_prevu__date=aujourdhui,
    ).exclude(statut='ANNULE').exists()


def a_acces_pos(employe, point_vente):
    return POSAccessService.can(
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.ACCEDER,
    )


@login_required
def liste_points_vente(request):
    points = POSAccessService.points_accessibles(user=request.user)
    if not points.exists():
        messages.error(
            request,
            "Aucun Bar ou Restaurant n'est accessible actuellement pour votre profil.",
        )
        return redirect('dashboard:index')

    context = {'points': points}
    return render(request, 'pos/selection.html', context)


@login_required
def pos_by_slug(request, slug):
    from ..constants import POINTS_VENTE_OPERATIONNELS
    point_vente = get_object_or_404(
        PointVente,
        code__iexact=slug,
        actif=True,
        type__in=POINTS_VENTE_OPERATIONNELS,
    )

    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employé trouvé.")
        return redirect('pos:liste_points_vente')

    access_decision = POSAccessService.check(
        user=request.user,
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.ACCEDER,
    )

    cpv = (
        CaissePointVente.objects
        .filter(point_vente=point_vente, actif=True)
        .select_related('caisse')
        .order_by('-principale', 'id')
        .first()
    )
    caisse = cpv.caisse if cpv else None
    session_non_finalisee = (
        get_session_non_finalisee_caisse(caisse)
        if caisse else None
    )
    session_close_allowed = False
    if (
        session_non_finalisee
        and session_non_finalisee.ouverte_par_id == employe.id
    ):
        session_close_allowed, _ = (
            CaisseSessionService.autoriser_finalisation_session(
                session_non_finalisee,
                employe,
            )
        )
    current_close_allowed = (
        POSAccessService.can(
            user=request.user,
            employe=employe,
            point_vente=point_vente,
            action=ActionPOS.FERMER_CAISSE,
        )
        if access_decision.allowed else False
    )
    can_close_cash = bool(session_close_allowed or current_close_allowed)
    finalisation_only = bool(
        not access_decision.allowed
        and session_close_allowed
    )

    if not access_decision.allowed and not finalisation_only:
        messages.error(
            request,
            f"Accès refusé à {point_vente.nom} ({access_decision.reason}).",
        )
        return redirect('pos:liste_points_vente')

    if not caisse or not caisse.actif:
        messages.error(request, "Caisse non configurée ou inactive")
        return redirect('pos:liste_points_vente')

    if (
        finalisation_only
        and session_non_finalisee
        and session_non_finalisee.statut == 'OUVERTE'
    ):
        session_non_finalisee = CaisseSessionService.demarrer_passation(
            session_non_finalisee,
            motif=f"Accès expiré: {access_decision.reason}",
            par=employe,
        )

    request.session['point_vente_courant_id'] = point_vente.id

    can_sell = False if finalisation_only else POSAccessService.can(
        user=request.user,
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.VENDRE,
    )
    can_cash = False if finalisation_only else POSAccessService.can(
        user=request.user,
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.ENCAISSER,
    )
    can_open_cash = False if finalisation_only else POSAccessService.can(
        user=request.user,
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.OUVRIR_CAISSE,
    )

    entrepot_ids = PointVenteService.get_entrepot_ids(point_vente)
    if not entrepot_ids and not finalisation_only:
        messages.error(
            request,
            "Ce point de vente n'est lié à aucun entrepôt. Contactez l'administrateur.",
        )
        return redirect('pos:liste_points_vente')

    produits = (
        Produit.objects.filter(actif=True, est_vendable=True)
        .select_related('categorie', 'domaine')
        if not finalisation_only
        else Produit.objects.none()
    )
    entrepots_disponibles = list(
        Entrepot.objects.filter(id__in=entrepot_ids, actif=True)
        .values('id', 'nom', 'type_entrepot')
    )
    stocks_par_entrepot = (
        PointVenteService.get_stocks_par_entrepot(entrepot_ids)
        if entrepot_ids else {}
    )
    stocks_dict = (
        PointVenteService.get_stocks_dict(entrepot_ids)
        if entrepot_ids else {}
    )
    menus = (
        MenuModel.objects.filter(actif=True, visible_dans_pos=True)
        .order_by('ordre_affichage', 'nom')
        if not finalisation_only
        else MenuModel.objects.none()
    )
    categories = PointVenteService.build_categories_dict(
        produits,
        menus,
        [],
        stocks_dict,
    )
    sous_categories = PointVenteService.build_sous_categories(categories)

    session_active = (
        session_non_finalisee
        if session_non_finalisee and session_non_finalisee.statut == 'OUVERTE'
        else None
    )
    owns_cash_session = bool(
        session_non_finalisee
        and session_non_finalisee.ouverte_par_id == employe.id
    )
    passation_payment_available = bool(
        session_non_finalisee
        and session_non_finalisee.statut == 'EN_PASSATION'
        and session_non_finalisee.ouverte_par_id == employe.id
        and employe.actif
        and bool(
            (session_non_finalisee.permissions_ouverture or {})
            .get('peut_encaisser')
        )
        and (
            session_non_finalisee.passation_jusqua is None
            or timezone.now() <= session_non_finalisee.passation_jusqua
        )
    )
    cash_payment_available = bool(
        (
            can_cash
            and session_active
            and session_active.ouverte_par_id == employe.id
        )
        or passation_payment_available
    )
    planning_actif = (
        ShiftEmploye.objects.filter(pk=access_decision.shift_id).first()
        if access_decision.allowed and access_decision.shift_id
        else None
    )

    entrepot_par_defaut = entrepot_ids[0] if entrepot_ids else None

    nouveau_planning = None
    if can_open_cash and not session_non_finalisee:
        expiration = access_decision.expires_at
        nouveau_planning = {
            'date': timezone.localdate().strftime('%d/%m/%Y'),
            'debut': (
                planning_actif.debut_prevu.strftime('%H:%M')
                if planning_actif else timezone.localtime().strftime('%H:%M')
            ),
            'fin': (
                planning_actif.fin_prevue.strftime('%H:%M')
                if planning_actif
                else expiration.strftime('%H:%M') if expiration
                else 'Sans limite'
            ),
            'mode_acces': access_decision.mode,
            'solde_initial': float(caisse.solde),
            'point_vente': point_vente.nom,
        }

    session_a_fermer = None
    if (
        session_non_finalisee
        and session_non_finalisee.ouverte_par_id == employe.id
        and can_close_cash
        and session_non_finalisee.statut in ('EN_PASSATION', 'EN_COMPTAGE')
    ):
        session_a_fermer = {
            'id': session_non_finalisee.id,
            'statut': session_non_finalisee.statut,
            'point_vente': point_vente.nom,
            'raison': (
                session_non_finalisee.motif_passation
                or access_decision.reason
            ),
            'solde_initial': float(session_non_finalisee.solde_initial),
            'total_ventes': float(session_non_finalisee.total_ventes),
            'especes_attendues': float(
                session_non_finalisee.solde_initial
                + session_non_finalisee.total_especes
            ),
            'total_carte': float(session_non_finalisee.total_carte),
            'total_mobile_money': float(session_non_finalisee.total_mobile_money),
            'total_cheque': float(session_non_finalisee.total_cheque),
            'date_passation': (
                session_non_finalisee.date_passation.isoformat()
                if session_non_finalisee.date_passation else None
            ),
            'passation_jusqua': (
                session_non_finalisee.passation_jusqua.isoformat()
                if session_non_finalisee.passation_jusqua else None
            ),
        }

    entreprise = Entreprise.objects.filter(actif=True).first()
    entreprise_nom = (
        entreprise.nom_commercial
        if entreprise and entreprise.nom_commercial
        else (entreprise.nom if entreprise else 'ERP Hôtelier')
    )

    page_config = {
        'categories': categories,
        'sous_categories': sous_categories,
        'active_categorie': None,
        'entrepots_disponibles': entrepots_disponibles,
        'entrepot_par_defaut': entrepot_par_defaut,
        'stocks_par_entrepot': stocks_par_entrepot,
        'point_vente_slug': point_vente.code,
        'point_vente_id': point_vente.id,
        'caisse_id': caisse.id,
        'employe_id': employe.id,
        'planning_fin_heure': (
            planning_actif.fin_prevue.strftime('%H:%M')
            if planning_actif else None
        ),
        'raf_depot_requis': (
            can_open_cash and caisse.solde == 0 and not session_non_finalisee
        ),
        'caisse_ouverte': session_active is not None,
        'session_a_fermer': session_a_fermer,
        'nouveau_planning': nouveau_planning,
        'entreprise_nom': entreprise_nom,
        'access_mode': access_decision.mode,
        'access_reason': access_decision.reason,
        'access_expires_at': (
            access_decision.expires_at.isoformat()
            if access_decision.expires_at else None
        ),
        'can_sell': can_sell,
        'can_cash': can_cash,
        'can_open_cash': can_open_cash,
        'can_close_cash': can_close_cash,
        'requires_cash_session': bool(
            can_cash or can_open_cash or finalisation_only
        ),
        'finalisation_only': finalisation_only,
        'owns_cash_session': owns_cash_session,
        'cash_payment_available': cash_payment_available,
        'cash_session_owner': (
            session_non_finalisee.ouverte_par.nom_complet
            if session_non_finalisee and session_non_finalisee.ouverte_par
            else None
        ),
    }

    context = {
        'point_vente': point_vente,
        'categories_json': json.dumps(categories, ensure_ascii=False),
        'sous_categories_json': json.dumps(sous_categories, ensure_ascii=False),
        'caisse_ouverte': session_active is not None,
        'session_active': session_active,
        'planning_expire': finalisation_only,
        'session_a_fermer_json': (
            json.dumps(session_a_fermer, ensure_ascii=False)
            if session_a_fermer else 'null'
        ),
        'nouveau_planning_json': (
            json.dumps(nouveau_planning, ensure_ascii=False)
            if nouveau_planning else 'null'
        ),
        'tables': [],
        'entrepots_disponibles_json': json.dumps(
            entrepots_disponibles,
            ensure_ascii=False,
        ),
        'entrepot_par_defaut': entrepot_par_defaut,
        'stocks_par_entrepot_json': json.dumps(
            stocks_par_entrepot,
            ensure_ascii=False,
        ),
        'raf_depot_requis': page_config['raf_depot_requis'],
        'session_active_id': session_active.id if session_active else None,
        'planning_fin_heure': page_config['planning_fin_heure'],
        'planning_debut_heure': (
            planning_actif.debut_prevu.strftime('%H:%M')
            if planning_actif else None
        ),
        'page_config': json.dumps(page_config, ensure_ascii=False),
        'access_mode': access_decision.mode,
        'access_reason': access_decision.reason,
        'access_expires_at': access_decision.expires_at,
        'can_sell': can_sell,
        'can_cash': can_cash,
        'can_open_cash': can_open_cash,
        'can_close_cash': can_close_cash,
        'finalisation_only': finalisation_only,
    }
    return render(request, 'pos/index.html', context)


@login_required
def pos_raf(request):
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employ\u00e9 trouv\u00e9.")
        return redirect('dashboard:index')

    point_vente = get_object_or_404(PointVente, code__iexact='RAF', actif=True)

    if not (
        request.user.is_superuser
        or request.user.groups.filter(name=RAF).exists()
    ):
        messages.error(request, "Non autorisé — le Guichet RAF reste hors du moteur POS Bar/Restaurant.")
        return redirect('dashboard:index')

    request.session['point_vente_courant_id'] = point_vente.id

    cpv = CaissePointVente.objects.filter(point_vente=point_vente, actif=True).select_related('caisse').first()
    caisse = cpv.caisse if cpv else None
    if not caisse or not caisse.actif:
        messages.error(request, "Caisse RAF non configur\u00e9e")
        return redirect('dashboard:index')

    entrepot_ids = list(PointVenteEntrepot.objects.filter(
        point_vente=point_vente
    ).values_list('entrepot_id', flat=True))
    if not entrepot_ids:
        messages.error(request, "Le Guichet RAF n'est li\u00e9 \u00e0 aucun entrep\u00f4t. Contactez l'administrateur.")
        return redirect('dashboard:index')

    mode = request.GET.get('mode', 'brasserie')
    if mode not in [m[0] for m in RAF_MODES]:
        mode = 'brasserie'

    from apps.hotel.models import UniteModel

    entreprise = Entreprise.objects.filter(actif=True).first()
    entreprise_nom = entreprise.nom_commercial if entreprise and entreprise.nom_commercial else (entreprise.nom if entreprise else 'ERP Hôtelier')

    produits = Produit.objects.filter(actif=True, est_vendable=True).select_related('categorie', 'domaine')

    entrepots_disponibles = list(Entrepot.objects.filter(
        id__in=entrepot_ids, actif=True
    ).values('id', 'nom', 'type_entrepot'))

    stocks_par_entrepot = {}
    for eid in entrepot_ids:
        st = StockEntrepot.objects.filter(entrepot_id=eid)
        stocks_par_entrepot[eid] = {s['produit_id']: float(s['quantite'])
            for s in st.values('produit_id', 'quantite')}

    stock_qs = StockEntrepot.objects.filter(entrepot_id__in=entrepot_ids)
    stocks_agg = stock_qs.values('produit_id').annotate(total=Sum('quantite'))
    stocks_dict = {s['produit_id']: float(s['total']) for s in stocks_agg}

    menus = MenuModel.objects.filter(actif=True, visible_dans_pos=True).order_by('ordre_affichage', 'nom')
    unites = UniteModel.objects.filter(actif=True).order_by('type_unite', 'code')

    categories = {}
    for p in produits:
        cat = p.domaine.nom.upper() if p.domaine else 'BRASSERIE'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            'id': p.id, 'nom': p.nom, 'prix': float(p.prix_vente),
            'code': p.code, 'image': p.image.url if p.image else None,
            'type': cat, 'article_type': 'PRODUIT',
            'stock': stocks_dict.get(p.id, 0), 'unite': p.unite_base,
            'sous_categorie': p.categorie.nom if p.categorie else None,
        })

    for m in menus:
        cat = 'RESTAURANT'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            'id': m.id, 'nom': m.nom, 'prix': float(m.prix_vente),
            'code': m.code, 'image': m.image.url if m.image else None,
            'type': cat, 'article_type': 'MENU', 'description': m.description or '',
            'sous_categorie': m.get_type_menu_display(),
        })

    for u in unites:
        cat = 'LOCATION'
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            'id': u.id, 'nom': f"{u.code} - {u.nom}", 'prix': float(u.prix),
            'prix_jour': float(u.prix_jour) if u.prix_jour else 0,
            'code': u.code, 'image': None,
            'type': cat, 'article_type': 'UNITE',
            'type_unite': u.type_unite, 'capacite': u.capacite,
            'statut_unite': u.statut,
            'sous_categorie': None,
        })

    session_active = CaisseSessionService.get_session_active(caisse)
    planning_actif = _get_planning_actif(employe, point_vente)

    mode_to_category = {'brasserie': 'BRASSERIE', 'restaurant': 'RESTAURANT', 'location': 'LOCATION'}
    cat_cible = mode_to_category.get(mode, 'BRASSERIE')

    if cat_cible in categories:
        active_categorie = cat_cible
    else:
        active_categorie = next(iter(categories), '')

    sous_categories = {}
    for cat, items in categories.items():
        scs = sorted(set(it['sous_categorie'] for it in items if it['sous_categorie']))
        if scs:
            sous_categories[cat] = scs

    nouveau_planning = {
        'debut': planning_actif.debut_prevu.strftime('%H:%M'),
        'fin': planning_actif.fin_prevue.strftime('%H:%M'),
        'solde_initial': float(caisse.solde),
        'point_vente': point_vente.nom,
    } if planning_actif and not session_active else None

    page_config = {
        'categories': categories,
        'sous_categories': sous_categories,
        'active_categorie': active_categorie,
        'entrepots_disponibles': entrepots_disponibles,
        'entrepot_par_defaut': entrepot_ids[0] if entrepot_ids else None,
        'stocks_par_entrepot': stocks_par_entrepot,
        'point_vente_slug': point_vente.code,
        'point_vente_id': point_vente.id,
        'caisse_id': caisse.id,
        'employe_id': employe.id if employe else None,
        'planning_fin_heure': planning_actif.fin_prevue.strftime('%H:%M') if planning_actif else None,
        'raf_depot_requis': False,
        'caisse_ouverte': session_active is not None,
        'session_a_fermer': None,
        'nouveau_planning': nouveau_planning,
        'entreprise_nom': entreprise_nom,
    }

    context = {
        'point_vente': point_vente,
        'categories_json': json.dumps(categories, ensure_ascii=False),
        'sous_categories_json': json.dumps(sous_categories, ensure_ascii=False),
        'caisse_ouverte': session_active is not None,
        'session_active': session_active,
        'planning_expire': False,
        'session_a_fermer_json': 'null',
        'nouveau_planning_json': json.dumps(nouveau_planning, ensure_ascii=False) if nouveau_planning else 'null',
        'tables': [],
        'is_raf': True, 'raf_mode': mode, 'raf_modes': RAF_MODES,
        'active_categorie': active_categorie,
        'entrepots_disponibles_json': json.dumps(entrepots_disponibles, ensure_ascii=False),
        'entrepot_par_defaut': entrepot_ids[0] if entrepot_ids else None,
        'stocks_par_entrepot_json': json.dumps(stocks_par_entrepot, ensure_ascii=False),
        'session_active_id': session_active.id if session_active else None,
        'planning_fin_heure': planning_actif.fin_prevue.strftime('%H:%M') if planning_actif else None,
        'planning_debut_heure': planning_actif.debut_prevu.strftime('%H:%M') if planning_actif else None,
        'page_config': json.dumps(page_config, ensure_ascii=False),
    }
    return render(request, 'pos/index.html', context)

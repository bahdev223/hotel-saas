from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from ..models import PointVente, PointVenteEntrepot, CaissePointVente
from ..services.pos_service import PointVenteService
from ..services.caisse_session_service import CaisseSessionService
from apps.tresorerie.models import Caisse
from apps.stock.models import Produit, StockEntrepot, Domaine, Entrepot
from apps.restaurant.models import MenuModel
from apps.authentication.groups import PATRON, MANAGER, BAR, RESTAURANT, CAISSIER, RAF
from apps.pos.models import AffectationPointVente, ShiftEmploye

def __get_planning_actif(employe, point_vente):
    from django.utils import timezone
    if not employe or not point_vente:
        return None
    now = timezone.localtime()
    affectation = AffectationPointVente.objects.filter(
        employe=employe, point_vente=point_vente, actif=True,
    ).first()
    if not affectation:
        return None
    return ShiftEmploye.objects.filter(
        affectation=affectation,
        debut_prevu__lte=now, fin_prevue__gte=now,
        statut__in=('PLANIFIE', 'CONFIRME', 'EN_COURS'),
    ).first()


RAF_MODES = [
    ('brasserie', 'Brasserie', '\U0001f37a'),
    ('restaurant', 'Restaurant', '\U0001f37d'),
    ('location', 'R\u00e9servation', '\U0001f3e8'),
]


def get_employe_pv_ids(employe):
    if not employe:
        return []
    return list(AffectationPointVente.objects.filter(employe=employe, actif=True).values_list('point_vente_id', flat=True))


GROUPES_VUE_GLOBALE = [PATRON, MANAGER, RAF]


def a_vue_globale_commandes(user):
    return user.groups.filter(name__in=GROUPES_VUE_GLOBALE).exists()


def get_pv_courant_id(request):
    pv_id = request.session.get('point_vente_courant_id')
    if pv_id:
        return pv_id
    employe = getattr(request.user, 'employe', None)
    pv_ids = get_employe_pv_ids(employe)
    return pv_ids[0] if pv_ids else None


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
    if not employe or not point_vente:
        return False
    pv_ids = get_employe_pv_ids(employe)
    if point_vente.id in pv_ids:
        return True
    return __get_planning_actif(employe, point_vente) is not None


@login_required
def liste_points_vente(request):
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employ\u00e9 trouv\u00e9.")
        return redirect('dashboard:index')

    pv_ids = get_employe_pv_ids(employe)
    for s in ShiftEmploye.objects.filter(
        affectation__employe=employe
    ).exclude(statut='ANNULE').select_related('affectation'):
        if s.affectation and s.affectation.point_vente_id:
            pv_ids.append(s.affectation.point_vente_id)

    pv_ids = list(set(pv_ids))
    if not pv_ids:
        messages.error(request, "Aucun point de vente trouv\u00e9 pour acc\u00e9der au POS.")
        return redirect('dashboard:index')

    points = PointVente.objects.filter(id__in=pv_ids, actif=True).distinct()
    context = {'points': points}
    return render(request, 'pos/selection.html', context)


@login_required
def pos_by_slug(request, slug):
    point_vente = get_object_or_404(PointVente, code__iexact=slug, actif=True)

    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employ\u00e9 trouv\u00e9.")
        return redirect('pos:liste_points_vente')

    if not a_acces_pos(employe, point_vente):
        messages.error(request, f"Non autoris\u00e9 \u2014 vous n'avez pas de planning pour {point_vente.nom}")
        return redirect('pos:liste_points_vente')

    request.session['point_vente_courant_id'] = point_vente.id

    cpv = CaissePointVente.objects.filter(point_vente=point_vente, actif=True).select_related('caisse').first()
    caisse = cpv.caisse if cpv else None
    if not caisse or not caisse.actif:
        messages.error(request, "Caisse non configur\u00e9e ou inactive")
        return redirect('pos:liste_points_vente')

    entrepot_ids = PointVenteService.get_entrepot_ids(point_vente)
    if not entrepot_ids:
        messages.error(request, "Ce point de vente n'est li\u00e9 \u00e0 aucun entrep\u00f4t. Contactez l'administrateur.")
        return redirect('pos:liste_points_vente')

    from apps.hotel.models import UniteModel

    produits = Produit.objects.filter(actif=True, est_vendable=True).select_related('categorie', 'domaine')
    entrepots_disponibles = list(Entrepot.objects.filter(
        id__in=entrepot_ids, actif=True
    ).values('id', 'nom', 'type_entrepot'))
    stocks_par_entrepot = PointVenteService.get_stocks_par_entrepot(entrepot_ids)
    stocks_dict = PointVenteService.get_stocks_dict(entrepot_ids)
    menus = MenuModel.objects.filter(actif=True, visible_dans_pos=True).order_by('ordre_affichage', 'nom')
    unites = UniteModel.objects.filter(actif=True).order_by('type_unite', 'code')
    categories = PointVenteService.build_categories_dict(produits, menus, unites, stocks_dict)
    sous_categories = PointVenteService.build_sous_categories(categories)

    session_active = CaisseSessionService.get_session_active(caisse)
    planning_actif = _get_planning_actif(employe, point_vente)

    entrepot_par_defaut = entrepot_ids[0] if entrepot_ids else None

    context = {
        'point_vente': point_vente,
        'categories_json': json.dumps(categories, ensure_ascii=False),
        'sous_categories_json': json.dumps(sous_categories, ensure_ascii=False),
        'caisse_ouverte': session_active is not None,
        'session_active': session_active,
        'planning_expire': False,
        'session_a_fermer_json': 'null',
        'nouveau_planning_json': json.dumps({
            'debut': planning_actif.debut_prevu.strftime('%H:%M'),
            'fin': planning_actif.fin_prevue.strftime('%H:%M'),
            'solde_initial': float(caisse.solde),
            'point_vente': point_vente.nom,
        }, ensure_ascii=False) if planning_actif and not session_active else 'null',
        'tables': [],
        'entrepots_disponibles_json': json.dumps(entrepots_disponibles, ensure_ascii=False),
        'entrepot_par_defaut': entrepot_par_defaut,
        'stocks_par_entrepot_json': json.dumps(stocks_par_entrepot, ensure_ascii=False),
        'raf_depot_requis': planning_actif is not None and caisse.solde == 0 and not session_active,
        'session_active_id': session_active.id if session_active else None,
        'planning_fin_heure': planning_actif.fin_prevue.strftime('%H:%M') if planning_actif else None,
        'planning_debut_heure': planning_actif.debut_prevu.strftime('%H:%M') if planning_actif else None,
    }
    return render(request, 'pos/index.html', context)


@login_required
def pos_raf(request):
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employ\u00e9 trouv\u00e9.")
        return redirect('dashboard:index')

    point_vente = get_object_or_404(PointVente, code__iexact='RAF', actif=True)

    if not a_acces_pos(employe, point_vente):
        messages.error(request, "Non autoris\u00e9 \u2014 vous n'avez pas de planning pour le Guichet RAF")
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

    context = {
        'point_vente': point_vente,
        'categories_json': json.dumps(categories, ensure_ascii=False),
        'sous_categories_json': json.dumps(sous_categories, ensure_ascii=False),
        'caisse_ouverte': session_active is not None,
        'session_active': session_active,
        'planning_expire': False,
        'session_a_fermer_json': 'null',
        'nouveau_planning_json': json.dumps({
            'debut': planning_actif.debut_prevu.strftime('%H:%M'),
            'fin': planning_actif.fin_prevue.strftime('%H:%M'),
            'solde_initial': float(caisse.solde),
            'point_vente': point_vente.nom,
        }, ensure_ascii=False) if planning_actif and not session_active else 'null',
        'tables': [],
        'is_raf': True, 'raf_mode': mode, 'raf_modes': RAF_MODES,
        'active_categorie': active_categorie,
        'entrepots_disponibles_json': json.dumps(entrepots_disponibles, ensure_ascii=False),
        'entrepot_par_defaut': entrepot_ids[0] if entrepot_ids else None,
        'stocks_par_entrepot_json': json.dumps(stocks_par_entrepot, ensure_ascii=False),
        'session_active_id': session_active.id if session_active else None,
        'planning_fin_heure': planning_actif.fin_prevue.strftime('%H:%M') if planning_actif else None,
        'planning_debut_heure': planning_actif.debut_prevu.strftime('%H:%M') if planning_actif else None,
    }
    return render(request, 'pos/index.html', context)

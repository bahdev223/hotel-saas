# apps/pos/views/pos.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import json
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from ..models import PointVente, PointVenteEntrepot, SessionPlanning
from ..services.pos_service import PointVenteService
from ..services.caisse_session_service import CaisseSessionService
from apps.tresorerie.models import Caisse
from apps.stock.models import Produit, StockEntrepot, Domaine, Entrepot
from apps.restaurant.models import MenuModel
from apps.authentication.groups import PATRON, MANAGER, BAR, RESTAURANT, CAISSIER, RAF

RAF_MODES = [
    ('brasserie', 'Brasserie', '🍺'),
    ('restaurant', 'Restaurant', '🍽'),
    ('location', 'Réservation', '🏨'),
]


def get_employe_point_vente(user):
    """Retourne le point_vente assigné à l'employé connecté, ou None"""
    employe = getattr(user, 'employe', None)
    return employe.point_vente if employe and employe.point_vente else None


# Groupes qui voient toutes les commandes de tous les points de vente
GROUPES_VUE_GLOBALE = [PATRON, MANAGER, RAF]


def a_vue_globale_commandes(user):
    """Patron / Manager / RAF voient toutes les commandes, tous PV confondus."""
    return user.groups.filter(name__in=GROUPES_VUE_GLOBALE).exists()


def get_pv_courant_id(request):
    """ID du point de vente où l'employé est connecté.

    Mémorisé en session à l'ouverture d'un POS (pos_by_slug / pos_raf).
    Fallback : le point de vente « maison » de l'employé.
    """
    pv_id = request.session.get('point_vente_courant_id')
    if pv_id:
        return pv_id
    employe = getattr(request.user, 'employe', None)
    return employe.point_vente_id if employe and employe.point_vente_id else None


def a_planning_aujourdhui(employe, point_vente):
    """Vérifie si l'employé a un planning aujourd'hui pour ce PV (sans restriction horaire)"""
    if not employe or not point_vente:
        return False
    aujourdhui = timezone.localtime().date()
    return SessionPlanning.objects.filter(
        employe=employe,
        point_vente=point_vente,
        date=aujourdhui,
    ).exclude(statut='ANNULE').exists()


def a_acces_pos(employe, point_vente):
    """Vérifie si l'employé a le droit d'accéder à ce PV (planning ACTIF maintenant OU point_vente direct)"""
    if not employe or not point_vente:
        return False
    if employe.point_vente_id == point_vente.id:
        return True
    from ..services.caisse_session_service import get_planning_actif
    return get_planning_actif(employe, point_vente) is not None


@login_required
def liste_points_vente(request):
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employé trouvé.")
        return redirect('dashboard:index')

    # PV où l'employé a un planning (sauf ANNULE) + son point_vente direct
    pv_ids = set()
    for pid in SessionPlanning.objects.filter(
        employe=employe
    ).exclude(statut='ANNULE').values_list('point_vente_id', flat=True):
        pv_ids.add(pid)
    if employe.point_vente:
        pv_ids.add(employe.point_vente_id)
    
    if not pv_ids:
        messages.error(request, "Aucun point de vente trouvé pour accéder au POS.")
        return redirect('dashboard:index')
    
    points = PointVente.objects.filter(id__in=pv_ids, actif=True).distinct()

    # Étape de sélection OBLIGATOIRE : plus jamais d'accès direct —
    # l'employé choisit explicitement son point de vente avant d'entrer.
    context = {'points': points}
    return render(request, 'pos/selection.html', context)


@login_required
def pos_by_slug(request, slug):
    point_vente = get_object_or_404(PointVente, code__iexact=slug, actif=True)
    
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employé trouvé.")
        return redirect('pos:liste_points_vente')
    
    if not a_acces_pos(employe, point_vente):
        messages.error(request, f"Non autorisé — vous n'avez pas de planning pour {point_vente.nom}")
        return redirect('pos:liste_points_vente')

    # Mémoriser le PV où l'employé est connecté (pour filtrer ses historiques)
    request.session['point_vente_courant_id'] = point_vente.id

    if not point_vente.caisse or not point_vente.caisse.actif:
        messages.error(request, "Caisse non configurée ou inactive")
        return redirect('pos:liste_points_vente')
    
    entrepot_ids = PointVenteService.get_entrepot_ids(point_vente)
    if not entrepot_ids:
        messages.error(request, "Ce point de vente n'est lié à aucun entrepôt. Contactez l'administrateur.")
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

    # Vérifier état session/planning (détection seule, pas de modification)
    etat_session = CaisseSessionService.verifier_session_planning(
        caisse=point_vente.caisse,
        employe=employe,
        point_vente=point_vente,
    )
    session_active = etat_session['session_active']
    planning_expire = etat_session['planning_expire']
    nouveau_planning = etat_session['nouveau_planning']

    entrepot_par_defaut = entrepot_ids[0] if entrepot_ids else None

    context = {
        'point_vente': point_vente,
        'categories_json': json.dumps(categories, ensure_ascii=False),
        'sous_categories_json': json.dumps(sous_categories, ensure_ascii=False),
        'caisse_ouverte': session_active is not None and not planning_expire,
        'session_active': session_active if not planning_expire else None,
        'planning_expire': planning_expire,
        'session_a_fermer_json': json.dumps(etat_session['session_a_fermer'], ensure_ascii=False) if etat_session['session_a_fermer'] else 'null',
        'nouveau_planning_json': json.dumps(nouveau_planning, ensure_ascii=False) if nouveau_planning else 'null',
        'tables': [],
        'entrepots_disponibles_json': json.dumps(entrepots_disponibles, ensure_ascii=False),
        'entrepot_par_defaut': entrepot_par_defaut,
        'stocks_par_entrepot_json': json.dumps(stocks_par_entrepot, ensure_ascii=False),
        'raf_depot_requis': nouveau_planning is not None and point_vente.caisse.solde == 0 and not planning_expire,
        'session_active_id': session_active.id if session_active else None,
        'planning_fin_heure': session_active.planning.heure_fin.strftime('%H:%M')
            if session_active and session_active.planning else None,
        'planning_debut_heure': session_active.planning.heure_debut.strftime('%H:%M')
            if session_active and session_active.planning else None,
    }
    return render(request, 'pos/index.html', context)


@login_required
def pos_raf(request):
    """Interface dédiée au Guichet RAF — planning requis"""
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employé trouvé.")
        return redirect('dashboard:index')

    point_vente = get_object_or_404(PointVente, code__iexact='RAF', actif=True)

    if not a_acces_pos(employe, point_vente):
        messages.error(request, "Non autorisé — vous n'avez pas de planning pour le Guichet RAF")
        return redirect('dashboard:index')

    # Mémoriser le PV où l'employé est connecté (pour filtrer ses historiques)
    request.session['point_vente_courant_id'] = point_vente.id

    if not point_vente.caisse or not point_vente.caisse.actif:
        messages.error(request, "Caisse RAF non configurée")
        return redirect('dashboard:index')

    # R1 : Vérifier que le PV RAF est lié à au moins un entrepôt
    entrepot_ids = list(PointVenteEntrepot.objects.filter(
        point_vente=point_vente
    ).values_list('entrepot_id', flat=True))
    if not entrepot_ids:
        messages.error(request, "Le Guichet RAF n'est lié à aucun entrepôt. Contactez l'administrateur.")
        return redirect('dashboard:index')

    # Mode depuis l'URL (brasserie | restaurant | location)
    mode = request.GET.get('mode', 'brasserie')
    if mode not in [m[0] for m in RAF_MODES]:
        mode = 'brasserie'

    from apps.hotel.models import UniteModel

    # Produits — toutes catégories
    produits = Produit.objects.filter(actif=True, est_vendable=True).select_related('categorie', 'domaine')

    # Entreprises disponibles pour le sélecteur (R2)
    entrepots_disponibles = list(Entrepot.objects.filter(
        id__in=entrepot_ids, actif=True
    ).values('id', 'nom', 'type_entrepot'))

    # Stock par entrepôt pour l'affichage individuel
    stocks_par_entrepot = {}
    for eid in entrepot_ids:
        st = StockEntrepot.objects.filter(entrepot_id=eid)
        stocks_par_entrepot[eid] = {s['produit_id']: float(s['quantite'])
            for s in st.values('produit_id', 'quantite')}

    # Stock agrégé (fallback)
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

    # Vérifier état session/planning (détection seule)
    etat_session = CaisseSessionService.verifier_session_planning(
        caisse=point_vente.caisse,
        employe=employe,
        point_vente=point_vente,
    )
    session_active = etat_session['session_active']
    planning_expire = etat_session['planning_expire']
    nouveau_planning = etat_session['nouveau_planning']

    # Filtrer les catégories selon le mode
    mode_to_category = {'brasserie': 'BRASSERIE', 'restaurant': 'RESTAURANT', 'location': 'LOCATION'}
    cat_cible = mode_to_category.get(mode, 'BRASSERIE')

    # Conserver toutes les catégories, le frontend filtre avec activeCategorie
    # Mais on définit la catégorie active par défaut
    if cat_cible in categories:
        active_categorie = cat_cible
    else:
        active_categorie = next(iter(categories), '')

    # Collecter les sous-catégories disponibles par catégorie
    sous_categories = {}
    for cat, items in categories.items():
        scs = sorted(set(it['sous_categorie'] for it in items if it['sous_categorie']))
        if scs:
            sous_categories[cat] = scs

    context = {
        'point_vente': point_vente,
        'categories_json': json.dumps(categories, ensure_ascii=False),
        'sous_categories_json': json.dumps(sous_categories, ensure_ascii=False),
        'caisse_ouverte': session_active is not None and not planning_expire,
        'session_active': session_active if not planning_expire else None,
        'planning_expire': planning_expire,
        'session_a_fermer_json': json.dumps(etat_session['session_a_fermer'], ensure_ascii=False) if etat_session['session_a_fermer'] else 'null',
        'nouveau_planning_json': json.dumps(nouveau_planning, ensure_ascii=False) if nouveau_planning else 'null',
        'tables': [],
        'is_raf': True,
        'raf_mode': mode,
        'raf_modes': RAF_MODES,
        'active_categorie': active_categorie,
        'entrepots_disponibles_json': json.dumps(entrepots_disponibles, ensure_ascii=False),
        'entrepot_par_defaut': entrepot_ids[0] if entrepot_ids else None,
        'stocks_par_entrepot_json': json.dumps(stocks_par_entrepot, ensure_ascii=False),
        'session_active_id': session_active.id if session_active else None,
        'planning_fin_heure': session_active.planning.heure_fin.strftime('%H:%M')
            if session_active and session_active.planning else None,
        'planning_debut_heure': session_active.planning.heure_debut.strftime('%H:%M')
            if session_active and session_active.planning else None,
    }
    return render(request, 'pos/index.html', context)


from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from datetime import date, timedelta

from apps.pos.models import Vente
from apps.hotel.models import UniteModel
from apps.bar.models import ProduitBar
from apps.restaurant.models import RecetteModel
from apps.rh.models import Employe, Contrat, Conge


@login_required
def index(request):
    """Dashboard principal"""
    today = date.today()

    # Taux d'occupation des chambres
    toutes_chambres = UniteModel.objects.filter(actif=True)
    total_chambres = toutes_chambres.count()
    chambres_occupees = toutes_chambres.filter(statut='OCCUPEE').count()
    taux_occupation = round((chambres_occupees / total_chambres * 100), 1) if total_chambres > 0 else 0

    # CA du jour depuis les ventes POS
    ca_jour = Vente.objects.filter(
        statut='PAYEE', created_at__date=today
    ).aggregate(total=Sum('montant_total'))['total'] or 0

    # Commandes en cours (ventes du jour)
    ventes_jour = Vente.objects.filter(created_at__date=today)
    total_commandes_en_cours = ventes_jour.count()
    commandes_restaurant = ventes_jour.filter(point_vente__emplacement='RESTAURANT').count()
    commandes_bar = ventes_jour.filter(point_vente__emplacement='BAR').count()
    commandes_room = 0

    # CA 7 derniers jours
    ca_7_jours = []
    for i in range(6, -1, -1):
        jour = today - timedelta(days=i)
        ca = Vente.objects.filter(
            statut='PAYEE', created_at__date=jour
        ).aggregate(total=Sum('montant_total'))['total'] or 0
        ca_7_jours.append({'date': jour.strftime('%d/%m'), 'ca': ca})

    # Chambres par type
    chambres_par_type = {}
    for ch in toutes_chambres:
        t = ch.type_unite or 'STANDARD'
        if t not in chambres_par_type:
            chambres_par_type[t] = {'total': 0, 'occupees': 0}
        chambres_par_type[t]['total'] += 1
        if ch.statut == 'OCCUPEE':
            chambres_par_type[t]['occupees'] += 1

    context = {
        'taux_occupation': taux_occupation,
        'chambres_occupees': chambres_occupees,
        'total_chambres': total_chambres,
        'ca_jour': ca_jour,
        'total_commandes_en_cours': total_commandes_en_cours,
        'commandes_restaurant': commandes_restaurant,
        'commandes_bar': commandes_bar,
        'commandes_room': commandes_room,
        'alertes_stock': 0,
        'reservations_aujourdhui': 0,
        'valeur_stock': 0,
        'ca_7_jours': ca_7_jours,
        'sources': {},
        'top_produits': [],
        'chambres_par_type': chambres_par_type,
        'activites_recentes': [],
        'titre': 'Tableau de bord'
    }
    return render(request, 'dashboard/index.html', context)


@login_required
def home(request):
    """Page d'accueil - Dashboard principal avec cartes"""
    today = date.today()

    # Chambres
    toutes_chambres = UniteModel.objects.filter(actif=True)
    total_chambres = toutes_chambres.count()
    chambres_occupees = toutes_chambres.filter(statut='OCCUPEE').count()
    taux_occupation = round((chambres_occupees / total_chambres * 100), 1) if total_chambres > 0 else 0

    # Commandes aujourd'hui
    ventes_jour = Vente.objects.filter(created_at__date=today)
    total_commandes_jour = ventes_jour.count()
    commandes_restaurant = ventes_jour.filter(point_vente__emplacement='RESTAURANT').count()
    commandes_bar = ventes_jour.filter(point_vente__emplacement='BAR').count()
    commandes_room = 0

    # CA du jour
    ca_jour = ventes_jour.filter(statut='PAYEE').aggregate(total=Sum('montant_total'))['total'] or 0

    # Stock bar
    valeur_stock_bar = sum(p.quantite_stock * p.prix for p in ProduitBar.objects.filter(actif=True)) if hasattr(ProduitBar, 'quantite_stock') else 0
    alertes_stock_bar = ProduitBar.objects.filter(actif=True).count() if not hasattr(ProduitBar, 'quantite_stock') else 0

    total_recettes = RecetteModel.objects.filter(actif=True).count()
    total_produits_bar = ProduitBar.objects.filter(actif=True).count()

    # RH
    nb_employes = Employe.objects.filter(actif=True).count()
    contrats_actifs = Contrat.objects.filter(actif=True).count()
    conges_attente = Conge.objects.filter(statut='En attente').count()

    cards = [
        {'id': 'chambres', 'title': 'Chambres', 'value': f"{chambres_occupees}/{total_chambres}", 'subtitle': f"{taux_occupation}% occupées", 'color': 'primary', 'icon': 'fa-bed', 'link': '/hotel/', 'bg_color': 'bg-primary/10'},
        {'id': 'commandes', 'title': 'Commandes', 'value': total_commandes_jour, 'subtitle': f"Resto: {commandes_restaurant} | Bar: {commandes_bar} | RS: {commandes_room}", 'color': 'warning', 'icon': 'fa-shopping-cart', 'link': '/restaurant/pos/', 'bg_color': 'bg-warning/10'},
        {'id': 'ca', 'title': 'CA du jour', 'value': f"{ca_jour:,.0f} F", 'subtitle': "Toutes sources confondues", 'color': 'success', 'icon': 'fa-chart-line', 'link': '/factures/', 'bg_color': 'bg-success/10'},
        {'id': 'stock', 'title': 'Stock Bar', 'value': f"{valeur_stock_bar:,.0f} F", 'subtitle': f"{alertes_stock_bar} alerte(s)", 'color': 'info', 'icon': 'fa-boxes', 'link': '/bar/produits/', 'bg_color': 'bg-info/10'},
        {'id': 'catalogue', 'title': 'Catalogue', 'value': total_recettes + total_produits_bar, 'subtitle': f"{total_recettes} plats | {total_produits_bar} boissons", 'color': 'secondary', 'icon': 'fa-utensils', 'link': '/restaurant/recettes/', 'bg_color': 'bg-secondary/10'},
        {'id': 'rh', 'title': 'Ressources Humaines', 'value': f"{contrats_actifs} contrats", 'subtitle': f"{nb_employes} employés · {conges_attente} congés en attente", 'color': 'info', 'icon': 'fa-users', 'link': '/rh/', 'bg_color': 'bg-info/10'},
    ]

    context = {
        'cards': cards,
        'activites_recentes': [],
        'user_role': request.user.groups.first().name if request.user.groups.first() else 'Administrateur',
        'titre': 'Tableau de bord'
    }
    return render(request, 'dashboard/home.html', context)

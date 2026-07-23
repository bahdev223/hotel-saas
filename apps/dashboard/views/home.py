from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Q

from apps.dashboard.services import (
    get_occupation,
    get_commandes_en_cours,
    get_alertes_stock,
    get_reservations_aujourdhui,
    get_ca_jour,
    get_ca_par_categorie,
    get_ca_hotel,
    get_ca_brasserie,
    get_ca_restaurant,
    get_ca_7_jours,
    get_ca_mensuel_par_categorie,
    get_ca_semaine,
    get_ca_mois,
    get_repartition_ca_7j,
    get_charges_par_domaine,
    get_top_produits,
    get_activites_recentes,
)


@login_required
def index(request):
    """Dashboard principal - Toutes les stats via les services."""

    periode = request.GET.get('periode', 'jour')

    if periode == 'semaine':
        ca_cats = get_ca_semaine()
        periode_label = 'Cette semaine'
    elif periode == 'mois':
        ca_cats = get_ca_mois()
        periode_label = 'Ce mois'
    else:
        ca_cats = get_ca_par_categorie()
        periode_label = "Aujourd'hui"

    occupation = get_occupation()
    commandes = get_commandes_en_cours()
    alertes = get_alertes_stock()
    repartition_ca = get_repartition_ca_7j()
    charges_par_domaine = get_charges_par_domaine()

    context = {
        'taux_occupation': occupation['taux'],
        'chambres_occupees': occupation['occupees'],
        'total_chambres': occupation['total'],

        'ca_total': ca_cats.get('total', sum(ca_cats.values())),
        'ca_hotel': ca_cats['hotel'],
        'ca_brasserie': ca_cats['brasserie'],
        'ca_restaurant': ca_cats['restaurant'],
        'periode_label': periode_label,
        'periode': periode,
        'ca_7_jours': get_ca_7_jours(),
        'ca_mensuel': get_ca_mensuel_par_categorie(),
        'repartition_ca': repartition_ca,
        'charges_par_domaine': charges_par_domaine,

        'total_commandes_en_cours': commandes['total'],
        'commandes_restaurant': commandes['restaurant'],
        'commandes_bar': commandes['bar'],
        'commandes_room': commandes['room_service'],

        'alertes_stock': alertes['total'],
        'reservations_aujourdhui': get_reservations_aujourdhui(),

        'top_produits': get_top_produits(),
        'activites_recentes': get_activites_recentes(),

        'titre': 'Tableau de bord',
    }

    return render(request, 'dashboard/index.html', context)


@login_required
def home(request):
    """Page d'accueil - Dashboard principal avec cartes"""
    from apps.clients.models import Client
    from apps.stock.models import Entrepot, StockEntrepot
    from apps.restaurant.models import TableModel, RecetteModel
    from apps.hotel.models import UniteModel
    from apps.pos.models import Commande

    bar_entrepot = Entrepot.objects.filter(type_entrepot='BAR', actif=True).first()

    occupation = get_occupation()
    commandes = get_commandes_en_cours()
    ca_jour = get_ca_jour()

    valeur_stock = 0
    alertes_stock_bar = 0
    total_produits_bar = 0

    if bar_entrepot:
        stocks_bar = StockEntrepot.objects.filter(entrepot=bar_entrepot).select_related('produit')
        valeur_stock = sum(float(s.quantite) * float(s.prix_achat or s.produit.prix_achat or 0) for s in stocks_bar)
        alertes_stock_bar = sum(1 for s in stocks_bar if s.quantite <= 0)
        total_produits_bar = stocks_bar.count()

    total_recettes = RecetteModel.objects.filter(actif=True).count()
    tables_occupees = TableModel.objects.filter(statut='OCCUPEE').count()

    cards = [
        {
            'id': 'chambres',
            'title': 'Chambres',
            'value': f"{occupation['occupees']}/{occupation['total']}",
            'subtitle': f"{occupation['taux']}% occupées",
            'color': 'primary',
            'icon': 'fa-bed',
            'link': '/hotel/',
            'bg_color': 'bg-primary/10'
        },
        {
            'id': 'commandes',
            'title': 'Commandes',
            'value': commandes['total'],
            'subtitle': f"Resto: {commandes['restaurant']} | Bar: {commandes['bar']} | RS: {commandes['room_service']}",
            'color': 'warning',
            'icon': 'fa-shopping-cart',
            'link': '/restaurant/pos/',
            'bg_color': 'bg-warning/10'
        },
        {
            'id': 'ca',
            'title': 'CA du jour',
            'value': f"{ca_jour:,.0f} F",
            'subtitle': "Toutes sources confondues",
            'color': 'success',
            'icon': 'fa-chart-line',
            'link': '/factures/',
            'bg_color': 'bg-success/10'
        },
        {
            'id': 'stock',
            'title': 'Stock Bar',
            'value': f"{valeur_stock:,.0f} F",
            'subtitle': f"{alertes_stock_bar} alerte(s)",
            'color': 'info',
            'icon': 'fa-boxes',
            'link': '/bar/produits/',
            'bg_color': 'bg-info/10'
        },
        {
            'id': 'catalogue',
            'title': 'Catalogue',
            'value': total_recettes + total_produits_bar,
            'subtitle': f"{total_recettes} plats | {total_produits_bar} boissons",
            'color': 'secondary',
            'icon': 'fa-utensils',
            'link': '/restaurant/recettes/',
            'bg_color': 'bg-secondary/10'
        },
        {
            'id': 'tables',
            'title': 'Tables',
            'value': tables_occupees,
            'subtitle': "Tables occupées",
            'color': 'error',
            'icon': 'fa-chair',
            'link': '/restaurant/plan/',
            'bg_color': 'bg-error/10'
        },
    ]

    context = {
        'cards': cards,
        'activites_recentes': get_activites_recentes(),
        'user_role': request.user.groups.first().name if request.user.groups.first() else 'Administrateur',
        'titre': 'Tableau de bord',
        'derniers_clients': Client.objects.exclude(
            Q(id=Client.PASSAGER_ID) | Q(telephone__startswith='PASSAGER-')
        ).order_by('-created_at')[:5],
    }

    return render(request, 'dashboard/home.html', context)

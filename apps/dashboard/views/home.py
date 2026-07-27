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
def home(request):
    """Page d'accueil - Dashboard complet avec KPIs, graphiques, activités"""
    from apps.clients.models import Client

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
    ca_7_jours_raw = get_ca_7_jours()
    ca_7_jours = {
        'labels': [d['date'] for d in ca_7_jours_raw],
        'hotel': [d['hotel'] for d in ca_7_jours_raw],
        'restaurant': [d['restaurant'] for d in ca_7_jours_raw],
        'brasserie': [d['brasserie'] for d in ca_7_jours_raw],
    }
    top_produits = get_top_produits()
    activites_recentes = get_activites_recentes()

    context = {
        'titre': 'Tableau de bord',
        'periode': periode,
        'periode_label': periode_label,

        'taux_occupation': occupation['taux'],
        'chambres_occupees': occupation['occupees'],
        'total_chambres': occupation['total'],

        'ca_total': ca_cats.get('total', sum(ca_cats.values())),
        'ca_hotel': ca_cats['hotel'],
        'ca_brasserie': ca_cats['brasserie'],
        'ca_restaurant': ca_cats['restaurant'],

        'ca_7_jours': ca_7_jours,
        'repartition_ca': repartition_ca,
        'charges_par_domaine': charges_par_domaine,

        'total_commandes_en_cours': commandes['total'],
        'commandes_restaurant': commandes['restaurant'],
        'commandes_bar': commandes['bar'],
        'commandes_room': commandes['room_service'],

        'alertes_stock': alertes['total'],
        'reservations_aujourdhui': get_reservations_aujourdhui(),

        'top_produits': top_produits,
        'activites_recentes': activites_recentes,

        'user_role': request.user.groups.first().name if request.user.groups.first() else 'Administrateur',
        'derniers_clients': Client.objects.exclude(
            Q(id=Client.PASSAGER_ID) | Q(telephone__startswith='PASSAGER-')
        ).order_by('-created_at')[:5],
    }

    return render(request, 'dashboard/home.html', context)


@login_required
def index(request):
    """Dashboard détaillé (mêmes données que home)"""
    return home(request)

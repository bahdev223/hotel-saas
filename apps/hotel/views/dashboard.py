# apps/hotel/views/dashboard.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import date

from ..models import UniteModel
from ..models.reservations import Reservation
from ..models.sejours import Sejour


@login_required
def dashboard(request):
    """Dashboard de l'hôtel"""
    
    # Stats unités
    total_unites = UniteModel.objects.filter(actif=True).count()
    unites_disponibles = UniteModel.objects.filter(statut='DISPONIBLE', actif=True).count()
    unites_occupees = UniteModel.objects.filter(statut='OCCUPEE', actif=True).count()
    taux_occupation = (unites_occupees / total_unites * 100) if total_unites > 0 else 0
    
    # Réservations en cours (confirmées)
    reservations_en_cours = Reservation.objects.filter(statut='CONFIRMEE').count()
    
    # Chiffre d'affaires du mois (via lignes de facture)
    from apps.facturation.models import LigneFactureModel
    mois_courant = date.today().month
    annee_courante = date.today().year
    lignes_mois = LigneFactureModel.objects.filter(
        facture__date_emission__year=annee_courante,
        facture__date_emission__month=mois_courant,
        facture__statut='PAYEE'
    )
    ca_mois = sum(l.total_ttc for l in lignes_mois)
    
    # Dernières réservations et séjours pour affichage
    dernieres_reservations = Reservation.objects.select_related('client').order_by('-id')[:5]
    sejours_actifs = Sejour.objects.select_related('client', 'chambre').filter(statut__in=['EN_COURS', 'CHECK_IN']).order_by('-id')[:5]
    
    # Arrivées et départs d'aujourd'hui
    today = timezone.now().date()
    arrivees_aujourdhui = Reservation.objects.filter(
        statut='CONFIRMEE',
        date_arrivee_prevue__date=today
    ).count()
    
    departs_aujourdhui = Sejour.objects.filter(
        statut__in=['EN_COURS', 'CHECK_IN'],
        date_depart__date=today
    ).count()
    
    context = {
        'total_unites': total_unites,
        'unites_disponibles': unites_disponibles,
        'unites_occupees': unites_occupees,
        'taux_occupation': round(taux_occupation, 1),
        'reservations_en_cours': reservations_en_cours,
        'ca_mois': ca_mois,
        'dernieres_reservations': dernieres_reservations,
        'sejours_actifs': sejours_actifs,
        'arrivees_aujourdhui': arrivees_aujourdhui,
        'departs_aujourdhui': departs_aujourdhui,
    }
    return render(request, 'hotel/dashboard/index.html', context)

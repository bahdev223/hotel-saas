# apps/hotel/views/dashboard.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from ..models import UniteModel, LocationModel


@login_required
def dashboard(request):
    """Dashboard de l'hôtel"""
    
    # Stats unités
    total_unites = UniteModel.objects.filter(actif=True).count()
    unites_disponibles = UniteModel.objects.filter(statut='DISPONIBLE', actif=True).count()
    unites_occupees = UniteModel.objects.filter(statut='OCCUPEE', actif=True).count()
    taux_occupation = (unites_occupees / total_unites * 100) if total_unites > 0 else 0
    
    # Locations en cours
    locations_en_cours = LocationModel.objects.filter(statut='CONFIRMEE').count()
    
    # Chiffre d'affaires du mois (via lignes de facture)
    from apps.facturation.models import LigneFactureModel
    from datetime import date
    mois_courant = date.today().month
    annee_courante = date.today().year
    lignes_mois = LigneFactureModel.objects.filter(
        facture__date_emission__year=annee_courante,
        facture__date_emission__month=mois_courant,
        facture__statut='PAYEE'
    )
    ca_mois = sum(l.total_ttc for l in lignes_mois)
    
    # Dernières locations
    dernieres_locations = LocationModel.objects.select_related('client', 'unite').order_by('-created_at')[:10]
    
    context = {
        'total_unites': total_unites,
        'unites_disponibles': unites_disponibles,
        'unites_occupees': unites_occupees,
        'taux_occupation': round(taux_occupation, 1),
        'locations_en_cours': locations_en_cours,
        'ca_mois': ca_mois,
        'dernieres_locations': dernieres_locations,
    }
    return render(request, 'hotel/dashboard/index.html', context)



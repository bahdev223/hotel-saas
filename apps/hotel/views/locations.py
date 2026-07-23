# apps/hotel/views/locations.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils import timezone
from decimal import Decimal
from datetime import datetime

from apps.clients.models import Client
from ..models import UniteModel, LocationModel


@login_required
def liste_locations(request):
    """Liste des locations"""
    locations = LocationModel.objects.select_related('client', 'unite').order_by('-date_debut')
    
    type_filter = request.GET.get('type')
    if type_filter:
        locations = locations.filter(type_location=type_filter)
    
    statut_filter = request.GET.get('statut')
    if statut_filter:
        locations = locations.filter(statut=statut_filter)
    
    paginator = Paginator(locations, 30)
    page = request.GET.get('page')
    locations_page = paginator.get_page(page)
    
    context = {
        'locations': locations_page,
        'type_choices': LocationModel.TYPE_CHOICES,
        'statut_choices': LocationModel.STATUT_CHOICES,
    }
    return render(request, 'hotel/locations/liste.html', context)


@login_required
def detail_location(request, location_id):
    """Détail d'une location"""
    location = get_object_or_404(LocationModel, id=location_id)
    
    context = {
        'location': location,
    }
    return render(request, 'hotel/locations/detail.html', context)


@login_required
def ajouter_sejour(request):
    """Ajouter une location de chambre avec génération automatique de facture"""
    if request.method == 'POST':
        try:
            from apps.facturation.services import FactureGenerators, FactureActions
            
            client_id = request.POST.get('client_id')
            unite_id = request.POST.get('unite_id')
            date_debut = datetime.strptime(request.POST.get('date_debut'), '%Y-%m-%dT%H:%M')
            duree_heures = int(request.POST.get('duree_heures', 1))
            
            unite = get_object_or_404(UniteModel, id=unite_id)
            
            if unite.statut != 'DISPONIBLE':
                messages.error(request, f'{unite.nom} ({unite.code}) non disponible')
                return redirect('hotel:ajouter_sejour')
            
            date_fin = date_debut + timezone.timedelta(hours=duree_heures)
            
            unite.occuper()

            location = LocationModel.objects.create(
                client_id=client_id,
                unite=unite,
                type_location='CHAMBRE',
                date_debut=date_debut,
                date_fin=date_fin,
                notes=request.POST.get('notes', ''),
            )
            location.calculer_montant_total()
            
            facture = FactureGenerators.depuis_location(location)
            facture.emettre()
            
            messages.success(
                request, 
                f'Location créée pour {location.client.nom_complet}. '
                f'Facture #{facture.numero} générée - Montant: {facture.montant_total:,.0f} F'
            )
            return redirect('hotel:detail_location', location_id=location.id)
            
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    context = {
        'clients': Client.objects.filter(statut='ACTIF'),
        'unites': UniteModel.objects.filter(actif=True, statut='DISPONIBLE', type_unite__in=['CHAMBRE', 'VIP']),
    }
    return render(request, 'hotel/locations/ajouter_sejour.html', context)


@login_required
def ajouter_evenement(request):
    """Ajouter une location d'espace/bar avec génération automatique de facture"""
    if request.method == 'POST':
        try:
            from apps.facturation.services import FactureGenerators, FactureActions
            
            client_id = request.POST.get('client_id')
            unite_id = request.POST.get('unite_id')
            date_debut = datetime.strptime(request.POST.get('date_debut'), '%Y-%m-%dT%H:%M')
            duree_heures = int(request.POST.get('duree_heures', 1))
            
            unite = get_object_or_404(UniteModel, id=unite_id)
            
            date_fin = date_debut + timezone.timedelta(hours=duree_heures)
            
            conflit = LocationModel.objects.filter(
                unite=unite,
                statut__in=['CONFIRMEE'],
                date_debut__lt=date_fin,
                date_fin__gt=date_debut
            ).exists()
            
            if conflit:
                messages.error(request, 'Cet espace est déjà occupé sur cette plage horaire')
                return redirect('hotel:ajouter_evenement')
            
            type_location = 'ESPACE'
            if unite.type_unite == 'BAR':
                type_location = 'BAR'
            
            unite.occuper()

            location = LocationModel.objects.create(
                client_id=client_id,
                unite=unite,
                type_location=type_location,
                date_debut=date_debut,
                date_fin=date_fin,
                notes=request.POST.get('notes', ''),
            )
            location.calculer_montant_total()
            
            facture = FactureGenerators.depuis_location(location)
            facture.emettre()
            
            messages.success(
                request, 
                f'Location créée pour {location.client.nom_complet}. '
                f'Facture #{facture.numero} générée - Montant: {facture.montant_total:,.0f} F'
            )
            return redirect('hotel:detail_location', location_id=location.id)
            
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    context = {
        'clients': Client.objects.filter(statut='ACTIF'),
        'unites': UniteModel.objects.filter(actif=True, type_unite__in=['ESPACE', 'BAR']),
    }
    return render(request, 'hotel/locations/ajouter_evenement.html', context)


@login_required
def check_out(request, location_id):
    """Check-out d'une location"""
    location = get_object_or_404(LocationModel, id=location_id)
    
    if request.method == 'POST':
        if location.statut == 'CONFIRMEE':
            location.terminer_auto()
            messages.success(request, f'Réservation terminée pour {location.client_nom or location.client.nom_complet}')
        else:
            messages.error(request, 'Impossible de terminer cette réservation')
        
        return redirect('hotel:detail_location', location_id=location.id)
    
    context = {'location': location}
    return render(request, 'hotel/locations/check_out.html', context)


@login_required
def annuler_location(request, location_id):
    """Annuler une location"""
    location = get_object_or_404(LocationModel, id=location_id)
    
    if request.method == 'POST':
        location.annuler()
        messages.success(request, 'Réservation annulée')
        return redirect('hotel:liste_locations')
    
    context = {'location': location}
    return render(request, 'hotel/locations/annuler.html', context)


# apps/hotel/views/unites.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator

from ..models import UniteModel

EQUIPEMENTS_LIST = ["Climatisation", "Wi-Fi", "TV", "Minibar", "Coffre-fort", "Sèche-cheveux", "Baignoire", "Douche", "Petit-déjeuner"]


@login_required
def liste_unites(request):
    """Liste des chambres"""
    unites = UniteModel.objects.filter(actif=True).order_by('type_unite', 'code')
    
    type_filter = request.GET.get('type')
    if type_filter:
        unites = unites.filter(type_unite=type_filter)
    
    statut_filter = request.GET.get('statut')
    if statut_filter:
        unites = unites.filter(statut=statut_filter)
    
    paginator = Paginator(unites, 20)
    page = request.GET.get('page')
    unites_page = paginator.get_page(page)
    
    context = {
        'unites': unites_page,
        'type_choices': [('CHAMBRE', 'Standard'), ('VIP', 'VIP')],
        'statut_choices': UniteModel.STATUT_CHOICES,
        'filtre_type': type_filter,
        'filtre_statut': statut_filter,
        'equipements_list': EQUIPEMENTS_LIST,
    }
    return render(request, 'hotel/unites/liste.html', context)


@login_required
def detail_unite(request, unite_id):
    """Détail d'une unité"""
    unite = get_object_or_404(UniteModel, id=unite_id)
    locations = unite.locations.all().select_related('client').order_by('-created_at')[:20]
    
    context = {
        'unite': unite,
        'locations': locations,
    }
    return render(request, 'hotel/unites/detail.html', context)


@login_required
def ajouter_unite(request):
    """Ajouter une unité"""
    if request.method == 'POST':
        try:
            unite = UniteModel.objects.create(
                code=request.POST.get('code'),
                nom=request.POST.get('nom'),
                type_unite=request.POST.get('type_unite'),
                capacite=request.POST.get('capacite', 1),
                surface_m2=request.POST.get('surface_m2') or None,
                equipements=request.POST.getlist('equipements'),
                prix=request.POST.get('prix'),
                description=request.POST.get('description', ''),
            )
            if 'image' in request.FILES:
                unite.image = request.FILES['image']
                unite.save()
            messages.success(request, f'{unite.nom} ({unite.code}) créée')
            return redirect('hotel:detail_unite', unite_id=unite.id)
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    context = {
        'type_choices': [('CHAMBRE', 'Standard'), ('VIP', 'VIP')],
        'equipements_list': EQUIPEMENTS_LIST,
    }
    return render(request, 'hotel/unites/ajouter.html', context)


@login_required
def modifier_unite(request, unite_id):
    """Modifier une unité"""
    unite = get_object_or_404(UniteModel, id=unite_id)
    
    if request.method == 'POST':
        try:
            unite.code = request.POST.get('code')
            unite.nom = request.POST.get('nom')
            unite.type_unite = request.POST.get('type_unite')
            unite.capacite = request.POST.get('capacite', 1)
            unite.surface_m2 = request.POST.get('surface_m2') or None
            unite.equipements = request.POST.getlist('equipements')
            unite.prix = request.POST.get('prix')
            unite.prix_jour = request.POST.get('prix_jour', 0)
            unite.description = request.POST.get('description', '')
            if 'image' in request.FILES:
                unite.image = request.FILES['image']
            unite.save()
            messages.success(request, f'{unite.nom} modifiée')
            return redirect('hotel:detail_unite', unite_id=unite.id)
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    context = {
        'unite': unite,
        'type_choices': [('CHAMBRE', 'Standard'), ('VIP', 'VIP')],
        'equipements_list': EQUIPEMENTS_LIST,
    }
    return render(request, 'hotel/unites/modifier.html', context)


@login_required
def changer_statut_unite(request, unite_id):
    """Changer le statut d'une unité"""
    unite = get_object_or_404(UniteModel, id=unite_id)
    
    if request.method == 'POST':
        nouveau_statut = request.POST.get('statut')
        if nouveau_statut in dict(UniteModel.STATUT_CHOICES):
            unite.statut = nouveau_statut
            unite.save()
            messages.success(request, f'Statut changé: {unite.get_statut_display()}')
    
    return redirect('hotel:detail_unite', unite_id=unite.id)


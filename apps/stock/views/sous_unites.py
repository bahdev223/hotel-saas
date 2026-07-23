# apps/stock/views/sous_unites.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
import uuid
from decimal import Decimal

from ..models import SousUnite, Produit
from ..constants import ALLOWED_STOCK_GROUPS


@login_required
def liste_sous_unites(request):
    """Liste des sous-unités"""
    sous_unites = SousUnite.objects.filter(actif=True).order_by('produit__nom', 'nom')
    
    context = {
        'sous_unites': sous_unites,
        'produits': Produit.objects.filter(actif=True),
    }
    return render(request, 'stock/sous_unites/liste.html', context)


@login_required
def ajouter_sous_unite(request):
    """Ajouter une sous-unité"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé. Vous n'êtes pas autorisé à accéder à cette page.")
        return redirect('admin:index')
    if request.method == 'POST':
        try:
            produit_id = request.POST.get('produit')
            nom = request.POST.get('nom')
            facteur = Decimal(request.POST.get('facteur', 1))
            prix = request.POST.get('prix') or None
            if prix:
                prix = Decimal(prix)
            
            sous_unite = SousUnite.objects.create(
                id=str(uuid.uuid4())[:8],
                produit_id=produit_id,
                nom=nom,
                facteur=facteur,
                prix=prix,
                actif=True
            )
            
            messages.success(request, f'Sous-unité {sous_unite.nom} ajoutée')
            return redirect('stock:liste_sous_unites')
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'produits': Produit.objects.filter(actif=True),
    }
    return render(request, 'stock/sous_unites/ajouter.html', context)


@login_required
def modifier_sous_unite(request, sous_unite_id):
    """Modifier une sous-unité"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé. Vous n'êtes pas autorisé à accéder à cette page.")
        return redirect('admin:index')
    sous_unite = get_object_or_404(SousUnite, id=sous_unite_id)
    
    if request.method == 'POST':
        try:
            sous_unite.produit_id = request.POST.get('produit')
            sous_unite.nom = request.POST.get('nom')
            sous_unite.facteur = Decimal(request.POST.get('facteur', 1))
            sous_unite.prix = request.POST.get('prix') or None
            if sous_unite.prix:
                sous_unite.prix = Decimal(sous_unite.prix)
            sous_unite.save()
            
            messages.success(request, f'Sous-unité {sous_unite.nom} modifiée')
            return redirect('stock:liste_sous_unites')
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'sous_unite': sous_unite,
        'produits': Produit.objects.filter(actif=True),
    }
    return render(request, 'stock/sous_unites/modifier.html', context)


@login_required
def supprimer_sous_unite(request, sous_unite_id):
    """Supprimer une sous-unité"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé. Vous n'êtes pas autorisé à accéder à cette page.")
        return redirect('admin:index')
    sous_unite = get_object_or_404(SousUnite, id=sous_unite_id)
    
    if request.method == 'POST':
        sous_unite.actif = False
        sous_unite.save()
        messages.success(request, f'Sous-unité {sous_unite.nom} supprimée')
        return redirect('stock:liste_sous_unites')
    
    context = {'sous_unite': sous_unite}
    return render(request, 'stock/sous_unites/supprimer.html', context)


@login_required
def api_sous_unite_par_produit(request, produit_id):
    """API pour récupérer les sous-unités d'un produit"""
    sous_unites = SousUnite.objects.filter(produit_id=produit_id, actif=True)
    
    data = {
        'sous_unites': [
            {
                'id': su.id,
                'nom': su.nom,
                'facteur': float(su.facteur),
                'prix': float(su.prix_reel),
            }
            for su in sous_unites
        ]
    }
    return JsonResponse(data)



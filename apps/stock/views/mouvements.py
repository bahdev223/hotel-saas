# apps/stock/views/mouvements.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from datetime import date
from decimal import Decimal

from ..models import MouvementStock, Produit, Entrepot, Fournisseur
from ..constants import ALLOWED_STOCK_GROUPS
from ..services.stock_service import StockService


@login_required
def liste_mouvements(request):
    """Redirige vers le dashboard"""
    from django.urls import reverse
    return redirect(reverse('stock:dashboard') + '?tab=stock')


@login_required
def entree_stock(request):
    """Formulaire d'entrÃ©e de stock"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    if request.method == 'POST':
        try:
            produit_id = request.POST.get('produit')
            quantite = Decimal(request.POST.get('quantite', 0))
            lot_numero = request.POST.get('lot_numero')
            date_peremption = request.POST.get('date_peremption')
            fournisseur_id = request.POST.get('fournisseur')
            prix_achat = Decimal(request.POST.get('prix_achat', 0))
            
            fournisseur = None
            if fournisseur_id:
                fournisseur = Fournisseur.objects.get(id=fournisseur_id)
            
            mouvement, lot = StockService.entree_stock(
                produit_id=produit_id,
                quantite=quantite,
                utilisateur=request.user.username,
                reference=lot_numero,
                prix_achat=prix_achat,
                fournisseur=fournisseur,
                lot_numero=lot_numero,
                date_peremption=date_peremption
            )
            
            messages.success(request, f'EntrÃ©e de {quantite} enregistrÃ©e')
            return redirect('stock:liste_mouvements')
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'produits': Produit.objects.filter(actif=True),
        'fournisseurs': Fournisseur.objects.filter(actif=True),
    }
    return render(request, 'stock/mouvements/entree.html', context)


@login_required
def sortie_stock(request):
    """Formulaire de sortie de stock"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    if request.method == 'POST':
        try:
            produit_id = request.POST.get('produit')
            quantite = Decimal(request.POST.get('quantite', 0))
            motif = request.POST.get('motif', 'perte')
            raison = request.POST.get('raison', '')
            
            mouvement = StockService.sortie_stock(
                produit_id=produit_id,
                quantite=quantite,
                utilisateur=request.user.username,
                motif=motif,
                raison=raison
            )
            
            messages.success(request, f'Sortie de {quantite} enregistrÃ©e')
            return redirect('stock:liste_mouvements')
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'produits': Produit.objects.filter(actif=True),
        'motifs': [
            ('perte', 'Perte / Casse / Vol'),
            ('consommation', 'Consommation interne'),
        ],
    }
    return render(request, 'stock/mouvements/sortie.html', context)




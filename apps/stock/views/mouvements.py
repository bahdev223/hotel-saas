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
    """Journal global des mouvements de stock, filtrable (produit, type,
    motif, entrepôt, période) — la vue d'audit du moteur de stock."""
    from ..enums.mouvements import TypeMouvement
    from ..enums.sources import SourceOperationType

    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé.")
        return redirect('admin:index')

    mouvements = MouvementStock.objects.select_related(
        'produit', 'entrepot_source', 'entrepot_dest', 'source_operation',
    ).order_by('-date_mouvement')

    f_q = request.GET.get('q', '').strip()
    f_type = request.GET.get('type', '')
    f_motif = request.GET.get('motif', '')
    f_entrepot = request.GET.get('entrepot', '')
    f_debut = request.GET.get('debut', '')
    f_fin = request.GET.get('fin', '')

    if f_q:
        mouvements = mouvements.filter(
            Q(produit__nom__icontains=f_q)
            | Q(produit__code__icontains=f_q)
            | Q(reference__icontains=f_q)
            | Q(raison__icontains=f_q)
        )
    if f_type:
        mouvements = mouvements.filter(type_mouvement=f_type)
    if f_motif:
        mouvements = mouvements.filter(motif=f_motif)
    if f_entrepot:
        mouvements = mouvements.filter(
            Q(entrepot_source_id=f_entrepot) | Q(entrepot_dest_id=f_entrepot)
        )
    if f_debut:
        mouvements = mouvements.filter(date_mouvement__date__gte=f_debut)
    if f_fin:
        mouvements = mouvements.filter(date_mouvement__date__lte=f_fin)

    paginator = Paginator(mouvements, 50)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'mouvements': page,
        'total_resultats': paginator.count,
        'entrepots': Entrepot.objects.filter(actif=True).order_by('nom'),
        'types_mouvement': TypeMouvement.choices,
        'motifs': SourceOperationType.choices,
        'f': {
            'q': f_q, 'type': f_type, 'motif': f_motif,
            'entrepot': f_entrepot, 'debut': f_debut, 'fin': f_fin,
        },
    }
    return render(request, 'stock/mouvements/liste.html', context)


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




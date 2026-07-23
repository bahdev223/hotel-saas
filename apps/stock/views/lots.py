# apps/stock/views/lots.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum
from datetime import date
import uuid
from decimal import Decimal

from ..models import Lot, Produit, Fournisseur
from ..constants import ALLOWED_STOCK_GROUPS


@login_required
def liste_lots(request):
    """Liste des lots"""
    lots = Lot.objects.filter(actif=True).order_by('-date_entree')
    
    # Filtres
    produit_id = request.GET.get('produit')
    est_perime = request.GET.get('est_perime')
    expire_bientot = request.GET.get('expire_bientot')
    search = request.GET.get('search')
    
    if produit_id:
        lots = lots.filter(produit_id=produit_id)
    if est_perime == 'oui':
        lots = lots.filter(date_peremption__lt=date.today())
    if expire_bientot == 'oui':
        from datetime import timedelta
        date_limite = date.today() + timedelta(days=30)
        lots = lots.filter(date_peremption__lte=date_limite, date_peremption__gte=date.today())
    if search:
        lots = lots.filter(numero__icontains=search)
    
    paginator = Paginator(lots, 20)
    page = request.GET.get('page')
    lots_page = paginator.get_page(page)
    
    context = {
        'lots': lots_page,
        'produits': Produit.objects.filter(actif=True),
        'total_quantite': lots.aggregate(total=Sum('quantite_restante'))['total'] or 0,
    }
    return render(request, 'stock/lots/liste.html', context)


@login_required
def detail_lot(request, lot_id):
    """Détail d'un lot"""
    lot = get_object_or_404(Lot, id=lot_id)
    
    # Mouvements liés à ce lot
    mouvements = lot.mouvements.all().order_by('-date_mouvement')[:20]
    
    context = {
        'lot': lot,
        'mouvements': mouvements,
    }
    return render(request, 'stock/lots/detail.html', context)


@login_required
def ajouter_lot(request):
    """Ajouter un lot manuellement"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé. Vous n'êtes pas autorisé à accéder à cette page.")
        return redirect('admin:index')
    if request.method == 'POST':
        try:
            produit_id = request.POST.get('produit')
            quantite = Decimal(request.POST.get('quantite', 0))
            numero = request.POST.get('numero')
            date_peremption = request.POST.get('date_peremption')
            fournisseur_id = request.POST.get('fournisseur')
            prix_achat = Decimal(request.POST.get('prix_achat', 0))
            
            if not numero:
                numero = f"LOT-{uuid.uuid4().hex[:8].upper()}"
            
            lot = Lot.objects.create(
                produit_id=produit_id,
                numero=numero,
                quantite=quantite,
                quantite_restante=quantite,
                date_peremption=date_peremption or None,
                fournisseur_id=fournisseur_id or None,
                prix_achat=prix_achat,
                actif=True
            )
            
            messages.success(request, f'Lot {lot.numero} ajouté avec succès')
            return redirect('stock:detail_lot', lot_id=lot.id)
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'produits': Produit.objects.filter(actif=True),
        'fournisseurs': Fournisseur.objects.filter(actif=True),
    }
    return render(request, 'stock/lots/ajouter.html', context)


@login_required
def modifier_lot(request, lot_id):
    """Modifier un lot"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé. Vous n'êtes pas autorisé à accéder à cette page.")
        return redirect('admin:index')
    lot = get_object_or_404(Lot, id=lot_id)
    
    if request.method == 'POST':
        try:
            lot.produit_id = request.POST.get('produit')
            lot.numero = request.POST.get('numero')
            lot.date_peremption = request.POST.get('date_peremption') or None
            lot.fournisseur_id = request.POST.get('fournisseur') or None
            lot.prix_achat = Decimal(request.POST.get('prix_achat', 0))
            lot.save()
            
            messages.success(request, f'Lot {lot.numero} modifié')
            return redirect('stock:detail_lot', lot_id=lot.id)
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'lot': lot,
        'produits': Produit.objects.filter(actif=True),
        'fournisseurs': Fournisseur.objects.filter(actif=True),
    }
    return render(request, 'stock/lots/modifier.html', context)


@login_required
def supprimer_lot(request, lot_id):
    """Supprimer un lot (soft delete)"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé. Vous n'êtes pas autorisé à accéder à cette page.")
        return redirect('admin:index')
    lot = get_object_or_404(Lot, id=lot_id)
    
    if request.method == 'POST':
        lot.actif = False
        lot.save()
        messages.success(request, f'Lot {lot.numero} supprimé')
        return redirect('stock:liste_lots')
    
    context = {'lot': lot}
    return render(request, 'stock/lots/supprimer.html', context)



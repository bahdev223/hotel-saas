# apps/stock/views/entrepots.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, Sum, F
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import json
import uuid

from ..models import Entrepot, Produit, StockEntrepot, MouvementStock, Domaine, CategorieProduit
from ..constants import ALLOWED_STOCK_GROUPS
from ..services.transfert_service import TransfertService


@login_required
def liste_entrepots(request):
    """Redirige vers le dashboard"""
    return redirect('stock:dashboard')


@login_required
def ajouter_entrepot(request):
    """Ajouter un entrepÃ´t"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    if request.method == 'POST':
        try:
            code = request.POST.get('code')
            nom = request.POST.get('nom')
            type_entrepot = request.POST.get('type_entrepot')
            
            if Entrepot.objects.filter(code=code).exists():
                messages.error(request, f'Le code {code} existe dÃ©jÃ ')
                return redirect('stock:ajouter_entrepot')
            
            entrepot = Entrepot.objects.create(
                code=code.upper(),
                nom=nom,
                type_entrepot=type_entrepot,
                actif=True
            )
            
            messages.success(request, f'EntrepÃ´t {entrepot.nom} crÃ©Ã© avec succÃ¨s')
            return redirect('stock:liste_entrepots')
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'types': Entrepot.TYPE_CHOICES,
    }
    return render(request, 'stock/entrepots/ajouter.html', context)


@login_required
def modifier_entrepot(request, entrepot_id):
    """Modifier un entrepÃ´t"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    entrepot = get_object_or_404(Entrepot, id=entrepot_id)
    
    if request.method == 'POST':
        try:
            if request.POST.get('code'):
                entrepot.code = request.POST.get('code').upper()
            entrepot.nom = request.POST.get('nom')
            entrepot.type_entrepot = request.POST.get('type_entrepot')
            entrepot.actif = request.POST.get('actif') == 'on'
            entrepot.responsable = request.POST.get('responsable', '')
            entrepot.save()
            
            messages.success(request, f'EntrepÃ´t {entrepot.nom} modifiÃ©')
            # Rediriger vers le détail si la requête vient du détail
            referer = request.META.get('HTTP_REFERER', '')
            if '/entrepots/' + str(entrepot_id) + '/' in referer:
                return redirect('stock:detail_entrepot', entrepot_id=entrepot.id)
            return redirect('stock:liste_entrepots')
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'entrepot': entrepot,
        'types': Entrepot.TYPE_CHOICES,
    }
    return render(request, 'stock/entrepots/modifier.html', context)


@login_required
def detail_entrepot(request, entrepot_id):
    """DÃ©tail d'un entrepÃ´t avec son stock"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    entrepot = get_object_or_404(Entrepot, id=entrepot_id)
    
    stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit')
    
    # Filtres
    search = request.GET.get('search')
    domaine_id = request.GET.get('domaine')
    categorie_id = request.GET.get('categorie')
    type_article = request.GET.get('type_article')
    statut_stock = request.GET.get('statut_stock')
    
    if search:
        stocks = stocks.filter(produit__nom__icontains=search)
    if domaine_id:
        stocks = stocks.filter(produit__domaine_id=domaine_id)
    if categorie_id:
        stocks = stocks.filter(produit__categorie_id=categorie_id)
    if type_article:
        stocks = stocks.filter(produit__type_article=type_article)
    if statut_stock:
        if statut_stock == 'rupture':
            stocks = stocks.filter(quantite__lte=0)
        elif statut_stock == 'alerte':
            stocks = stocks.filter(quantite__gt=0, quantite__lte=F('produit__seuil_alerte'))
        elif statut_stock == 'ok':
            stocks = stocks.filter(quantite__gt=F('produit__seuil_alerte'))
    
    # Ajouter le stock converti pour chaque produit
    stocks_with_converti = []
    for stock in stocks:
        produit = stock.produit
        quantite = int(stock.quantite)
        
        # Calculer le stock converti
        if produit.sous_unites.exists():
            result = []
            reste = quantite
            sous_unites_triees = produit.sous_unites.filter(actif=True).order_by('-facteur')
            
            for su in sous_unites_triees:
                facteur = int(su.facteur)
                if facteur > 0 and reste >= facteur:
                    nb = reste // facteur
                    result.append(f"{nb} {su.nom}")
                    reste = reste % facteur
            
            if reste > 0 or not result:
                result.append(f"{reste} {produit.unite_base}")
            stock_converti = ", ".join(result)
        else:
            stock_converti = f"{quantite} {produit.unite_base}"
        
        stocks_with_converti.append({
            'produit': produit,
            'quantite': quantite,
            'valeur': float(quantite) * float(stock.prix_achat or stock.produit.prix_achat or 0),
            'stock_converti': stock_converti
        })
    
    # Pagination
    paginator = Paginator(stocks_with_converti, 20)
    page = request.GET.get('page')
    stocks_page = paginator.get_page(page)

    from urllib.parse import urlencode
    params_base = {k: v for k, v in request.GET.items() if k != 'page'}
    params_str = '&' + urlencode(params_base) if params_base else ''
    
    # Statistiques
    stats = {
        'total_produits': len(stocks_with_converti),
        'valeur_stock': sum(item['valeur'] for item in stocks_with_converti),
        'rupture': sum(1 for s in stocks_with_converti if s['quantite'] <= 0),
        'alerte': sum(1 for s in stocks_with_converti if 0 < s['quantite'] <= s['produit'].seuil_alerte),
    }
    
    context = {
        'entrepot': entrepot,
        'stocks': stocks_page,
        'stocks_full': stocks_with_converti,
        'stats': stats,
        'search': search,
        'params_str': params_str,
        'domaine_id': domaine_id,
        'categorie_id': categorie_id,
        'type_article': type_article,
        'statut_stock': statut_stock,
        'domaines': Domaine.objects.filter(actif=True).order_by('ordre', 'nom'),
        'categories': CategorieProduit.objects.filter(actif=True).order_by('nom'),
        'types_article': Produit.TYPE_ARTICLE_CHOICES,
        'derniers_mouvements': MouvementStock.objects.filter(
            Q(entrepot_source=entrepot) | Q(entrepot_dest=entrepot)
        ).select_related('produit', 'entrepot_source', 'entrepot_dest').order_by('-date_mouvement')[:15],
    }
    return render(request, 'stock/entrepots/detail.html', context)


@login_required
def transfert_produits(request):
    """Interface de transfert entre entrepÃ´ts"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    if request.method == 'POST':
        try:
            produit_id = request.POST.get('produit_id')
            quantite = Decimal(request.POST.get('quantite', 0))
            source_id = request.POST.get('source_id')
            dest_id = request.POST.get('dest_id')
            
            transfert = TransfertService.transfert_entre_entrepots(
                produit_id=produit_id,
                quantite=quantite,
                entrepot_source_id=source_id,
                entrepot_dest_id=dest_id,
                utilisateur=request.user.username,
                reference=request.POST.get('reference', ''),
                notes=request.POST.get('notes', '')
            )
            
            messages.success(request, f'Transfert effectuÃ© avec succÃ¨s')
            return redirect('stock:liste_transferts')
            
        except Exception as e:
            messages.error(request, str(e))
    
    entrepots = Entrepot.objects.filter(actif=True)
    produits = Produit.objects.filter(actif=True)
    
    context = {
        'entrepots': entrepots,
        'produits': produits,
    }
    return render(request, 'stock/transferts/transfert.html', context)


@login_required
def liste_transferts(request):
    """Historique des transferts"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    transferts = MouvementStock.objects.filter(type_mouvement='TRANSFERT').order_by('-date_mouvement')
    
    # Filtres
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    if date_debut:
        transferts = transferts.filter(date_mouvement__date__gte=date_debut)
    if date_fin:
        transferts = transferts.filter(date_mouvement__date__lte=date_fin)
    
    paginator = Paginator(transferts, 30)
    page = request.GET.get('page')
    transferts_page = paginator.get_page(page)
    
    context = {
        'transferts': transferts_page,
        'entrepots': Entrepot.objects.filter(actif=True),
    }
    return render(request, 'stock/transferts/liste.html', context)


@csrf_exempt
@login_required
def api_stock_entrepot(request, entrepot_id, produit_id):
    """API pour rÃ©cupÃ©rer le stock d'un produit dans un entrepÃ´t"""
    try:
        stock = StockEntrepot.objects.get(entrepot_id=entrepot_id, produit_id=produit_id)
        return JsonResponse({
            'success': True,
            'quantite': float(stock.quantite),
            'unite': stock.produit.unite_base
        })
    except StockEntrepot.DoesNotExist:
        return JsonResponse({'success': True, 'quantite': 0})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def api_supprimer_stock_entrepot(request, entrepot_id, produit_id):
    """API pour supprimer un produit d'un entrepôt (uniquement si stock=0 et aucun historique)"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    try:
        stock = get_object_or_404(StockEntrepot, entrepot_id=entrepot_id, produit_id=produit_id)

        if stock.quantite > 0:
            return JsonResponse({'success': False, 'error': 'Impossible : stock > 0. Faites d\'abord une sortie.'})

        a_des_mouvements = MouvementStock.objects.filter(
            Q(entrepot_source_id=entrepot_id) | Q(entrepot_dest_id=entrepot_id),
            produit_id=produit_id
        ).exists()

        if a_des_mouvements:
            return JsonResponse({'success': False, 'error': 'Ce produit a un historique (ventes, transferts, inventaire). Suppression impossible.'})

        stock.delete()
        return JsonResponse({'success': True, 'message': 'Produit retiré de cet entrepôt'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


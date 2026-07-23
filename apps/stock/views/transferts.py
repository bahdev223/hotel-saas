# apps/stock/views/transferts.py
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
from decimal import Decimal
import json
from datetime import date

from ..models import MouvementStock, Produit, Entrepot
from ..constants import ALLOWED_STOCK_GROUPS
from ..services.transfert_service import TransfertService


@login_required
def liste_transferts(request):
    """Redirige vers le dashboard"""
    return redirect('stock:dashboard')


@login_required
def transfert_produits(request):
    """Formulaire de transfert entre entrepôts"""
    from django.urls import reverse
    if request.method == 'POST':
        try:
            source_id = request.POST.get('source_id')
            dest_id = request.POST.get('dest_id')
            produit_id = request.POST.get('produit_id')
            quantite = request.POST.get('quantite')
            sous_unite_id = request.POST.get('sous_unite_id')
            
            mouvement = TransfertService.transfert_entre_entrepots(
                produit_id=produit_id,
                quantite=quantite,
                entrepot_source_id=source_id,
                entrepot_dest_id=dest_id,
                utilisateur=request.user.username,
                reference=request.POST.get('reference', ''),
                notes=request.POST.get('notes', ''),
                sous_unite_id=sous_unite_id if sous_unite_id else None
            )
            messages.success(request, 'Transfert effectué avec succès')
            return redirect('stock:liste_transferts')
        except Exception as e:
            messages.error(request, str(e))
    
    return redirect(reverse('stock:dashboard') + '?tab=transferts')


@csrf_exempt
def api_transfert_bar(request):
    """API pour transfert vers le Bar avec sous-unitÃ©s"""
    
    # VÃ©rifier les droits
    if request.user.is_authenticated:
        user_groups = request.user.groups.values_list('name', flat=True)
        if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
            return JsonResponse({'success': False, 'error': 'â›” AccÃ¨s refusÃ©'}, status=403)
    else:
        return JsonResponse({'success': False, 'error': 'Non authentifiÃ©'}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            print(f"ðŸ“¦ DonnÃ©es reÃ§ues: {data}")
            
            produit_id = data.get('produit_id')
            quantite = data.get('quantite')
            sous_unite_id = data.get('sous_unite_id')
            
            if not produit_id:
                return JsonResponse({'success': False, 'error': 'Produit non spÃ©cifiÃ©'})
            
            if not quantite or Decimal(str(quantite)) <= 0:
                return JsonResponse({'success': False, 'error': 'QuantitÃ© invalide'})
            
            # RÃ©cupÃ©rer ou crÃ©er l'entrepÃ´t bar
            bar_entrepot, created = Entrepot.objects.get_or_create(
                code='BAR001',
                defaults={
                    'nom': 'BAR',
                    'type_entrepot': 'BAR',
                    'actif': True
                }
            )
            
            # RÃ©cupÃ©rer l'entrepÃ´t source (stock central)
            source_entrepot = Entrepot.objects.filter(
                type_entrepot='CENTRAL',
                actif=True
            ).first()
            
            if not source_entrepot:
                source_entrepot = Entrepot.objects.filter(
                    nom__icontains='CENTRAL'
                ).first()
            
            if not source_entrepot:
                source_entrepot = Entrepot.objects.create(
                    code='STK001',
                    nom='STOCK CENTRAL',
                    type_entrepot='CENTRAL',
                    actif=True
                )
            
            print(f"ðŸ“ Source: {source_entrepot.nom} (ID: {source_entrepot.id})")
            print(f"ðŸ“ Destination: {bar_entrepot.nom} (ID: {bar_entrepot.id})")
            
            mouvement = TransfertService.transfert_entre_entrepots(
                produit_id=produit_id,
                quantite=quantite,
                entrepot_source_id=source_entrepot.id,
                entrepot_dest_id=bar_entrepot.id,
                utilisateur=request.user.username,
                reference=data.get('reference', ''),
                notes=data.get('notes', ''),
                sous_unite_id=sous_unite_id if sous_unite_id else None
            )
            
            return JsonResponse({'success': True, 'mouvement_id': mouvement.id})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'POST required'})


@csrf_exempt
def api_transfert_restaurant(request):
    """API pour transfert vers le Restaurant avec sous-unitÃ©s"""
    
    # VÃ©rifier les droits
    if request.user.is_authenticated:
        user_groups = request.user.groups.values_list('name', flat=True)
        if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
            return JsonResponse({'success': False, 'error': 'â›” AccÃ¨s refusÃ©'}, status=403)
    else:
        return JsonResponse({'success': False, 'error': 'Non authentifiÃ©'}, status=401)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            produit_id = data.get('produit_id')
            quantite = data.get('quantite')
            sous_unite_id = data.get('sous_unite_id')
            
            if not produit_id:
                return JsonResponse({'success': False, 'error': 'Produit non spÃ©cifiÃ©'})
            
            if not quantite or Decimal(str(quantite)) <= 0:
                return JsonResponse({'success': False, 'error': 'QuantitÃ© invalide'})
            
            # RÃ©cupÃ©rer ou crÃ©er l'entrepÃ´t restaurant
            restau_entrepot, created = Entrepot.objects.get_or_create(
                code='RST001',
                defaults={
                    'nom': 'RESTAURANT',
                    'type_entrepot': 'RESTAURANT',
                    'actif': True
                }
            )
            
            # RÃ©cupÃ©rer l'entrepÃ´t source (stock central)
            source_entrepot = Entrepot.objects.filter(
                type_entrepot='CENTRAL',
                actif=True
            ).first()
            
            if not source_entrepot:
                source_entrepot = Entrepot.objects.filter(
                    nom__icontains='CENTRAL'
                ).first()
            
            if not source_entrepot:
                source_entrepot = Entrepot.objects.create(
                    code='STK001',
                    nom='STOCK CENTRAL',
                    type_entrepot='CENTRAL',
                    actif=True
                )
            
            mouvement = TransfertService.transfert_entre_entrepots(
                produit_id=produit_id,
                quantite=quantite,
                entrepot_source_id=source_entrepot.id,
                entrepot_dest_id=restau_entrepot.id,
                utilisateur=request.user.username,
                reference=data.get('reference', ''),
                notes=data.get('notes', ''),
                sous_unite_id=sous_unite_id if sous_unite_id else None
            )
            
            return JsonResponse({'success': True, 'mouvement_id': mouvement.id})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'POST required'})


@csrf_exempt
@login_required
def api_transfert_entrepot(request):
    """API gÃ©nÃ©rique pour transfert entre entrepÃ´ts"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        return JsonResponse({'success': False, 'error': 'â›” AccÃ¨s refusÃ©'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body)
        
        # Effectuer le transfert
        mouvement = TransfertService.transfert_entre_entrepots(
            produit_id=data.get('produit_id'),
            quantite=data.get('quantite'),
            entrepot_source_id=data.get('source_id'),
            entrepot_dest_id=data.get('dest_id'),
            utilisateur=request.user.username,
            reference=data.get('reference', ''),
            notes=data.get('notes', ''),
            sous_unite_id=data.get('sous_unite_id')
        )
        
        return JsonResponse({'success': True, 'mouvement_id': mouvement.id})
        
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def api_annuler_transfert(request, mouvement_id):
    """Annule un transfert (réservé RAF) — inverse SORTIE et ENTREE."""
    from ..models.mouvement_stock import MouvementStock
    from ..services.transfert_service import TransfertService

    if not request.user.groups.filter(name='RAF').exists():
        return JsonResponse({'success': False, 'error': 'Réservé au RAF'}, status=403)

    try:
        mouvement = MouvementStock.objects.get(id=mouvement_id)
        TransfertService.annuler_transfert(mouvement, request.user.username)
        return JsonResponse({'success': True, 'message': 'Transfert annulé'})
    except MouvementStock.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Mouvement introuvable'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


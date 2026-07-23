# apps/stock/views/entrees.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction as db_transaction
from decimal import Decimal
import json
from datetime import datetime

from ..models import Produit, Entrepot, MouvementStock
from ..services import MouvementStockService


@login_required
def liste_entrees(request):
    """Redirige vers le dashboard"""
    from django.urls import reverse
    return redirect(reverse('stock:dashboard') + '?tab=stock')


@login_required
def api_liste_entrees(request):
    """API pour lister les entrÃ©es"""
    mouvements = MouvementStock.objects.filter(
        type_mouvement='ENTREE', motif='achat'
    ).order_by('-date_mouvement')[:100]
    
    # Grouper par rÃ©fÃ©rence
    entrees_dict = {}
    for m in mouvements:
        ref = m.reference or f"ID-{m.id}"
        if ref not in entrees_dict:
            entrees_dict[ref] = {
                'id': m.id,
                'date': m.date_mouvement,
                'reference': ref,
                'fournisseur': 'EntrÃ©e stock',
                'produits_count': 0,
                'produits_liste': []
            }
        entrees_dict[ref]['produits_count'] += 1
        entrees_dict[ref]['produits_liste'].append(m.produit.nom)
    
    # Transformer en liste
    entrees = []
    for item in entrees_dict.values():
        item['produits_liste'] = ', '.join(item['produits_liste'][:3])
        if len(item['produits_liste'].split(',')) > 3:
            item['produits_liste'] += '...'
        entrees.append(item)
    
    return JsonResponse({'success': True, 'entrees': entrees})


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def api_ajouter_entree(request):
    """API ultra simple pour ajouter une entrÃ©e stock"""
    try:
        data = json.loads(request.body)
        
        # GÃ©nÃ©rer une rÃ©fÃ©rence
        reference = f"ENT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # RÃ©cupÃ©rer l'entrepÃ´t central
        central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
        if not central:
            central = Entrepot.objects.create(
                code='STK001',
                nom='STOCK CENTRAL',
                type_entrepot='CENTRAL',
                actif=True
            )
        
        lignes_ajoutees = 0
        
        # Pour chaque ligne
        with db_transaction.atomic():
            for ligne in data.get('lignes', []):
                produit_id = ligne.get('produit_id')
                quantite = Decimal(str(ligne.get('quantite', 0)))
                prix = Decimal(str(ligne.get('prix', 0)))
                
                if not produit_id or quantite <= 0:
                    continue
                
                # Entrée stock via le moteur unique
                MouvementStockService.entree_stock(
                    produit=Produit.objects.get(id=produit_id),
                    entrepot=central,
                    quantite=quantite,
                    utilisateur=request.user.username,
                    motif='achat',
                    valeur_unitaire=float(prix),
                    reference=reference,
                    raison="Entrée stock"
                )
                
                # Mettre à jour le prix d'achat si fourni
                if prix > 0:
                    Produit.objects.filter(id=produit_id).update(prix_achat=prix)
                
                lignes_ajoutees += 1
        
        if lignes_ajoutees == 0:
            return JsonResponse({'success': False, 'error': 'Aucun produit valide'})
        
        return JsonResponse({'success': True, 'reference': reference, 'lignes': lignes_ajoutees})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})
    
    


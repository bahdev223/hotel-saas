# apps/restaurant/views/cuisine.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json

from apps.pos.models import Commande, LigneCommande


@login_required
def cuisine_dashboard(request):
    """Écran cuisine - affiche les commandes à préparer (depuis POS)"""
    return render(request, 'restaurant/cuisine/dashboard.html')


@login_required
def api_cuisine_commandes(request):
    """API pour récupérer les commandes à préparer depuis POS"""
    # Commandes de type restaurant ou bar qui ne sont pas encore servies
    commandes = Commande.objects.filter(
        statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRETE'],
        type_commande__in=['SUR_PLACE', 'EMPORTER']  # Commandes restaurant
    ).select_related('table', 'point_vente').order_by('-created_at')

    data = []
    for commande in commandes:
        temps_attente = int((timezone.now() - commande.created_at).total_seconds() / 60)

        lignes = []
        for ligne in commande.lignes.all():
            # Récupérer le nom du produit ou menu
            if ligne.produit:
                nom = ligne.produit.nom
            elif ligne.menu:
                nom = ligne.menu.nom
            else:
                nom = "Article"
            
            lignes.append({
                'nom': nom,
                'quantite': float(ligne.quantite),
                'notes': ligne.notes or ""
            })

        data.append({
            'id': commande.id,
            'numero': commande.numero,
            'table': commande.table.numero if commande.table else 'Emporter',
            'point_vente': commande.point_vente.nom if commande.point_vente else '',
            'type': commande.get_type_commande_display(),
            'statut': commande.statut,
            'statut_display': commande.get_statut_display(),
            'temps_attente': temps_attente,
            'lignes': lignes,
            'notes': commande.notes or ""
        })

    return JsonResponse({'success': True, 'commandes': data})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_cuisine_changer_statut(request, commande_id):
    """Changer le statut d'une commande (en préparation, prêt, servi)"""
    try:
        commande = get_object_or_404(Commande, id=commande_id)

        if request.content_type == 'application/json':
            data = json.loads(request.body)
            nouveau_statut = data.get('statut')
        else:
            nouveau_statut = request.POST.get('statut')

        # Mapping des statuts POS
        statut_mapping = {
            'EN_PREPARATION': 'EN_PREPARATION',
            'PRETE': 'PRETE',
            'SERVIE': 'SERVIE'
        }
        
        if nouveau_statut and nouveau_statut in statut_mapping:
            if nouveau_statut == 'EN_PREPARATION':
                commande.passer_en_preparation()
            elif nouveau_statut == 'PRETE':
                commande.marquer_prete()
            elif nouveau_statut == 'SERVIE':
                commande.servir()
            
            # 🔥 Optionnel : Déstocker les ingrédients quand commande en préparation
            if nouveau_statut == 'EN_PREPARATION':
                from ..services.production_service import destocker_commande
                destocker_commande(commande)

        return JsonResponse({'success': True, 'statut': commande.statut})

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_cuisine_historique(request):
    """API pour l'historique des commandes servies"""
    commandes = Commande.objects.filter(
        statut__in=['SERVIE', 'LIVREE']
    ).select_related('table').order_by('-updated_at')[:50]

    data = []
    for commande in commandes:
        data.append({
            'id': commande.id,
            'numero': commande.numero,
            'table': commande.table.numero if commande.table else 'Emporter',
            'date': commande.updated_at.strftime('%d/%m/%Y %H:%M'),
            'montant': float(commande.montant_total)
        })

    return JsonResponse({'success': True, 'commandes': data})


@login_required
def api_cuisine_commande_detail(request, commande_id):
    """API pour le détail d'une commande"""
    commande = get_object_or_404(Commande, id=commande_id)

    lignes = []
    for ligne in commande.lignes.all():
        if ligne.produit:
            nom = ligne.produit.nom
        elif ligne.menu:
            nom = ligne.menu.nom
        else:
            nom = "Article"
            
        lignes.append({
            'id': ligne.id,
            'nom': nom,
            'quantite': float(ligne.quantite),
            'prix_unitaire': float(ligne.prix_unitaire),
            'total': float(ligne.quantite * ligne.prix_unitaire),
            'notes': ligne.notes
        })

    return JsonResponse({
        'success': True,
        'commande': {
            'id': commande.id,
            'numero': commande.numero,
            'table': commande.table.numero if commande.table else 'Emporter',
            'type': commande.get_type_commande_display(),
            'statut': commande.statut,
            'statut_display': commande.get_statut_display(),
            'date': commande.created_at.strftime('%d/%m/%Y %H:%M'),
            'lignes': lignes,
            'montant_total': float(commande.montant_total),
            'notes': commande.notes
        }
    })

# apps/restaurant/views/cuisine.py - AJOUTER CES FONCTIONS

@login_required
def api_commande_ingredients(request, commande_id):
    """Récupère les ingrédients nécessaires pour une commande"""
    commande = get_object_or_404(Commande, id=commande_id)
    
    ingredients = []
    stock_manquant = []
    
    from apps.stock.models import Entrepot, StockEntrepot
    entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    
    for ligne in commande.lignes.all():
        if ligne.menu:
            # C'est un menu → chercher les recettes du menu
            for ligne_menu in ligne.menu.lignes.all():
                if ligne_menu.recette:
                    for ingredient in ligne_menu.recette.ingredients.all():
                        quantite = ingredient.quantite * ligne.quantite
                        
                        # Vérifier le stock
                        stock = StockEntrepot.objects.filter(
                            entrepot=entrepot, 
                            produit=ingredient.produit
                        ).first()
                        stock_qte = stock.quantite if stock else Decimal('0')
                        
                        ingredients.append({
                            'id': ingredient.produit.id,
                            'nom': ingredient.produit.nom,
                            'quantite': float(quantite),
                            'unite': ingredient.produit.unite_base,
                            'stock': float(stock_qte),
                            'disponible': stock_qte >= quantite
                        })
                        
                        if stock_qte < quantite:
                            stock_manquant.append({
                                'produit': ingredient.produit.nom,
                                'requis': float(quantite),
                                'disponible': float(stock_qte),
                                'unite': ingredient.produit.unite_base
                            })
        
        elif ligne.produit:
            # C'est un produit direct
            quantite = ligne.quantite
            stock = StockEntrepot.objects.filter(
                entrepot=entrepot, 
                produit=ligne.produit
            ).first()
            stock_qte = stock.quantite if stock else Decimal('0')
            
            ingredients.append({
                'id': ligne.produit.id,
                'nom': ligne.produit.nom,
                'quantite': float(quantite),
                'unite': ligne.produit.unite_base,
                'stock': float(stock_qte),
                'disponible': stock_qte >= quantite
            })
            
            if stock_qte < quantite:
                stock_manquant.append({
                    'produit': ligne.produit.nom,
                    'requis': float(quantite),
                    'disponible': float(stock_qte),
                    'unite': ligne.produit.unite_base
                })
    
    return JsonResponse({
        'success': True,
        'ingredients': ingredients,
        'stock_manquant': stock_manquant
    })


@login_required
@csrf_exempt
def api_lancer_cuisson(request, commande_id):
    """Lance la cuisson - déstockage selon mode choisi"""
    try:
        commande = get_object_or_404(Commande, id=commande_id)
        data = json.loads(request.body)
        mode = data.get('mode', 'auto')
        ingredients_manuels = data.get('ingredients', [])
        
        from apps.stock.models import Entrepot, StockEntrepot, MouvementStock
        
        entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
        if not entrepot:
            return JsonResponse({'success': False, 'error': 'Entrepôt restaurant non trouvé'})
        
        # Récupérer les ingrédients à déstocker
        ingredients_a_destock = []
        
        if mode == 'manuel':
            # Mode manuel : utiliser les ingrédients sélectionnés
            for ing in ingredients_manuels:
                produit = get_object_or_404(Produit, id=ing['id'])
                ingredients_a_destock.append({
                    'produit': produit,
                    'quantite': Decimal(str(ing['quantite'])),
                    'nom': produit.nom
                })
        else:
            # Mode auto ou semi : utiliser les recettes
            for ligne in commande.lignes.all():
                if ligne.menu:
                    for ligne_menu in ligne.menu.lignes.all():
                        if ligne_menu.recette:
                            for ingredient in ligne_menu.recette.ingredients.all():
                                ingredients_a_destock.append({
                                    'produit': ingredient.produit,
                                    'quantite': ingredient.quantite * ligne.quantite,
                                    'nom': ingredient.produit.nom
                                })
                elif ligne.produit:
                    ingredients_a_destock.append({
                        'produit': ligne.produit,
                        'quantite': ligne.quantite,
                        'nom': ligne.produit.nom
                    })
        
        # Grouper par produit (fusionner les quantités)
        grouped = {}
        for ing in ingredients_a_destock:
            key = ing['produit'].id
            if key not in grouped:
                grouped[key] = {'produit': ing['produit'], 'quantite': Decimal('0'), 'nom': ing['nom']}
            grouped[key]['quantite'] += ing['quantite']
        
        # Vérifier le stock
        stock_insuffisant = []
        for ing in grouped.values():
            stock = StockEntrepot.objects.filter(entrepot=entrepot, produit=ing['produit']).first()
            stock_qte = stock.quantite if stock else Decimal('0')
            if stock_qte < ing['quantite']:
                stock_insuffisant.append({
                    'produit': ing['nom'],
                    'requis': float(ing['quantite']),
                    'disponible': float(stock_qte)
                })
        
        if stock_insuffisant:
            return JsonResponse({
                'success': False,
                'error': 'Stock insuffisant',
                'details': stock_insuffisant
            })
        
        # Déstocker
        mouvements = []
        for ing in grouped.values():
            stock = StockEntrepot.objects.get(entrepot=entrepot, produit=ing['produit'])
            
            MouvementStock.objects.create(
                produit=ing['produit'],
                type_mouvement='SORTIE',
                quantite=ing['quantite'],
                entrepot_source=entrepot,
                reference=f"CUISSON-{commande.numero}",
                raison=f"Préparation commande #{commande.numero}",
                utilisateur=request.user.username
            )
            
            stock.quantite -= ing['quantite']
            stock.save()
            
            mouvements.append({
                'produit': ing['nom'],
                'quantite': float(ing['quantite'])
            })
        
        # Marquer la commande comme en préparation
        commande.passer_en_preparation()
        
        return JsonResponse({
            'success': True,
            'message': f'Cuisson lancée pour commande #{commande.numero}',
            'mouvements': mouvements
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
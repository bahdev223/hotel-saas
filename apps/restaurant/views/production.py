# apps/restaurant/views/production.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from decimal import Decimal
import json
from datetime import date, timedelta

from ..models import MenuModel, Production, ProductionLigne, RecetteModel
from ..services.production_service import ProductionService
from apps.stock.models import Entrepot, StockEntrepot, Produit
from apps.rh.models import Employe


@login_required
def production_dashboard(request):
    """Dashboard production cuisine"""
    
    # Récupérer l'entrepôt RESTAURANT
    entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    
    # Récupérer tous les menus actifs
    menus = MenuModel.objects.filter(actif=True, visible_dans_pos=True)
    
    # Préparer les données des menus avec stock
    menus_avec_stock = []
    for menu in menus:
        # Vérifier si une recette existe
        recette = RecetteModel.objects.filter(menu_associe=menu).first()
        
        # Calculer le nombre de portions possibles avec le stock actuel
        portions_possibles = None
        if recette and entrepot:
            portions_possibles = menu.verifier_disponibilite(entrepot)
        
        menus_avec_stock.append({
            'id': menu.id,
            'code': menu.code,
            'nom': menu.nom,
            'prix_vente': float(menu.prix_vente),
            'image': menu.image.url if menu.image else None,
            'a_recette': recette is not None,
            'portions_possibles': portions_possibles.get('disponible', False) if portions_possibles else None,
            'manques': portions_possibles.get('manques', []) if portions_possibles else []
        })
    
    # Dernières productions
    dernieres_productions = Production.objects.all().order_by('-date')[:10]
    
    # Statistiques du jour
    stats = ProductionService.get_stats_journalieres(date.today())
    
    context = {
        'menus': menus_avec_stock,
        'dernieres_productions': dernieres_productions,
        'entrepot': entrepot,
        'stats': stats,
    }
    return render(request, 'restaurant/production/dashboard.html', context)


@login_required
def production_liste(request):
    """Liste des productions"""
    
    productions = Production.objects.all().order_by('-date')
    
    # Filtres
    statut = request.GET.get('statut')
    if statut:
        productions = productions.filter(statut=statut)
    
    paginator = Paginator(productions, 20)
    page = request.GET.get('page')
    productions_page = paginator.get_page(page)
    
    context = {
        'productions': productions_page,
        'statut_choices': Production.STATUT_CHOICES,
    }
    return render(request, 'restaurant/production/liste.html', context)


@login_required
def production_detail(request, production_id):
    """Détail d'une production"""
    
    production = get_object_or_404(Production, id=production_id)
    lignes = production.lignes.all()
    ingredients = production.ingredients.all()
    
    # Vérification stock
    verification = production.verifier_stock()
    
    context = {
        'production': production,
        'lignes': lignes,
        'ingredients': ingredients,
        'verification': verification,
    }
    return render(request, 'restaurant/production/detail.html', context)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_produire(request):
    """API pour créer et valider une production"""
    
    try:
        data = json.loads(request.body)
        menu_id = data.get('menu_id')
        quantite = Decimal(str(data.get('quantite', 0)))
        
        if quantite <= 0:
            return JsonResponse({'success': False, 'error': 'Quantité invalide'})
        
        menu = get_object_or_404(MenuModel, id=menu_id)
        
        # Vérifier que le menu a une recette
        if not menu.recette:
            return JsonResponse({
                'success': False,
                'error': f'Le menu {menu.nom} n\'a pas de recette associée'
            })
        
        # Récupérer l'entrepôt RESTAURANT
        entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
        if not entrepot:
            entrepot = Entrepot.objects.create(
                code='RESTAURANT',
                nom='Restaurant Principal',
                type_entrepot='RESTAURANT',
                actif=True
            )
        
        # Créer la production
        production = ProductionService.creer_production(
            entrepot_source=entrepot,
            entrepot_dest=entrepot,
            notes=f"Production de {quantite} {menu.nom}"
        )
        
        # Ajouter le menu
        ProductionService.ajouter_menu(production, menu, quantite)
        
        # Valider la production
        employe = Employe.objects.filter(user=request.user).first()
        if not employe:
            employe = Employe.objects.first()
        
        ProductionService.valider_production(production, employe.id if employe else None)
        
        return JsonResponse({
            'success': True,
            'message': f'✅ {quantite} {menu.nom} produit(s)',
            'production_id': production.id,
            'numero': production.numero
        })
        
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_annuler_production(request, production_id):
    """API pour annuler une production"""
    
    try:
        production = get_object_or_404(Production, id=production_id)
        production.annuler()
        
        return JsonResponse({
            'success': True,
            'message': f'Production #{production.numero} annulée'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_verifier_stock(request, menu_id):
    """API pour vérifier le stock disponible pour un menu"""
    
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
        
        if not menu.recette:
            return JsonResponse({
                'success': False,
                'error': 'Aucune recette définie'
            })
        
        verification = menu.verifier_disponibilite(entrepot)
        
        return JsonResponse({
            'success': True,
            'disponible': verification['disponible'],
            'manques': verification['manques']
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_historique_production(request):
    """API pour récupérer l'historique des productions"""
    
    try:
        # Paramètres de filtrage
        jours = int(request.GET.get('jours', 30))
        statut = request.GET.get('statut')
        
        date_debut = date.today() - timedelta(days=jours)
        
        productions = Production.objects.filter(
            date__date__gte=date_debut
        ).order_by('-date')
        
        if statut:
            productions = productions.filter(statut=statut)
        
        # Pagination
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        
        paginator = Paginator(productions, per_page)
        productions_page = paginator.get_page(page)
        
        # Formatage des données
        data = []
        for p in productions_page:
            data.append({
                'id': p.id,
                'numero': p.numero,
                'date': p.date.strftime('%d/%m/%Y %H:%M'),
                'statut': p.statut,
                'total_menus': float(p.total_menus),
                'produit_par': p.produit_par.username if p.produit_par else None,
                'lignes': [
                    {
                        'menu': l.menu.nom,
                        'quantite': float(l.quantite)
                    }
                    for l in p.lignes.all()
                ]
            })
        
        return JsonResponse({
            'success': True,
            'productions': data,
            'total': paginator.count,
            'page': page,
            'total_pages': paginator.num_pages
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_production_detail(request, production_id):
    """API pour récupérer le détail d'une production"""
    
    try:
        production = get_object_or_404(Production, id=production_id)
        
        # Lignes de production
        lignes = []
        for l in production.lignes.all():
            lignes.append({
                'menu_id': l.menu.id,
                'menu_nom': l.menu.nom,
                'quantite': float(l.quantite)
            })
        
        # Ingrédients consommés
        ingredients = []
        for i in production.ingredients.all():
            ingredients.append({
                'produit_id': i.produit.id,
                'produit_nom': i.produit.nom,
                'quantite': float(i.quantite),
                'unite': i.unite or i.produit.unite_base
            })
        
        return JsonResponse({
            'success': True,
            'production': {
                'id': production.id,
                'numero': production.numero,
                'date': production.date.strftime('%d/%m/%Y %H:%M'),
                'statut': production.statut,
                'notes': production.notes,
                'lignes': lignes,
                'ingredients': ingredients,
                'total_menus': float(production.total_menus)
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_stock_menu(request, menu_id):
    """API pour récupérer le stock d'un menu (produit fini)"""
    
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        
        # Récupérer l'entrepôt RESTAURANT
        entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
        
        if not entrepot:
            return JsonResponse({
                'success': True,
                'stock': 0,
                'message': 'Aucun entrepôt RESTAURANT configuré'
            })
        
        # Chercher le produit associé au menu
        produit = Produit.objects.filter(code=menu.code).first()
        
        if not produit:
            return JsonResponse({
                'success': True,
                'stock': 0,
                'message': 'Aucun produit associé à ce menu'
            })
        
        # Récupérer le stock
        stock = StockEntrepot.objects.filter(
            entrepot=entrepot,
            produit=produit
        ).first()
        
        stock_qte = float(stock.quantite) if stock else 0
        
        # Vérifier la disponibilité des ingrédients
        verification = None
        if menu.recette:
            verification = menu.recette.verifier_disponibilite(entrepot)
        
        return JsonResponse({
            'success': True,
            'stock': stock_qte,
            'unite': 'pièce',
            'disponibilite_ingredients': verification
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
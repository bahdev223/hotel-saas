# apps/restaurant/views/api.py
import json
import uuid
from decimal import Decimal

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from django.db import models

from ..models import RecetteModel, IngredientModel, MenuModel, LigneMenuModel
from apps.stock.models import Produit, StockEntrepot, Entrepot


@login_required
def api_produits(request):
    """API pour récupérer les produits (AJAX)"""
    produits = Produit.objects.filter(actif=True, domaine__nom='RESTAURANT')
    data = [
        {
            'id': p.id,
            'nom': p.nom,
            'prix': float(p.prix_vente) if p.prix_vente else 0,
            'stock': 0,  # À calculer si besoin
            'categorie': p.categorie.nom if p.categorie else ''
        }
        for p in produits
    ]
    return JsonResponse({'produits': data}, safe=False)


@login_required
def api_statistiques(request):
    """API pour les statistiques (AJAX)"""
    from apps.restaurant.models import VenteModel, RecetteModel
    from datetime import date, timedelta
    
    today = date.today()
    week_ago = today - timedelta(days=7)
    
    # CA du jour
    ca_jour = VenteModel.objects.filter(
        date_vente__date=today
    ).aggregate(total=models.Sum('montant_total'))['total'] or 0
    
    # CA semaine
    ca_semaine = VenteModel.objects.filter(
        date_vente__date__gte=week_ago
    ).aggregate(total=models.Sum('montant_total'))['total'] or 0
    
    # Nombre de recettes
    nb_recettes = RecetteModel.objects.filter(actif=True).count()
    
    return JsonResponse({
        'ca_jour': float(ca_jour),
        'ca_semaine': float(ca_semaine),
        'nb_recettes': nb_recettes,
        'top_ventes': []
    })


@login_required
def api_dashboard(request):
    """API JSON - Données du tableau de bord restaurant"""
    from datetime import date, timedelta, datetime
    from apps.pos.models import Commande, Vente, LigneCommande
    from django.db.models import Q
    from ..models import FileAttenteModel, Production

    today = date.today()
    now = datetime.now()
    restaurant_entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()

    # ── Ventes du jour (payées) ──
    ventes_jour = Vente.objects.filter(created_at__date=today, statut='PAYEE')
    ca_jour = float(ventes_jour.aggregate(total=models.Sum('montant_total'))['total'] or 0)
    nb_ventes_jour = ventes_jour.count()

    # ── Commandes du jour ──
    commandes_jour = Commande.objects.filter(created_at__date=today)
    nb_commandes_jour = commandes_jour.count()
    commandes_attente = commandes_jour.filter(statut='EN_ATTENTE').count()
    commandes_preparation = commandes_jour.filter(statut='EN_PREPARATION').count()

    # ── CA semaine ──
    week_ago = today - timedelta(days=7)
    ca_semaine = float(Vente.objects.filter(created_at__date__gte=week_ago, statut='PAYEE')
                       .aggregate(total=models.Sum('montant_total'))['total'] or 0)

    # ── CA 7 derniers jours (pour mini graphique) ──
    ca_7jours = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        total = float(Vente.objects.filter(created_at__date=d, statut='PAYEE')
                      .aggregate(t=models.Sum('montant_total'))['t'] or 0)
        ca_7jours.append({'date': d.strftime('%a %d/%m'), 'total': total})

    # ── Stock alerte ──
    stock_alertes = []
    if restaurant_entrepot:
        stocks = StockEntrepot.objects.filter(
            entrepot=restaurant_entrepot,
            produit__actif=True,
            produit__est_vendable=True,
            quantite__lte=models.F('produit__seuil_alerte'),
        ).select_related('produit')[:8]
        stock_alertes = [
            {
                'produit_id': s.produit_id,
                'produit_nom': s.produit.nom,
                'produit_code': s.produit.code,
                'stock': float(s.quantite),
                'seuil': float(s.produit.seuil_alerte),
            }
            for s in stocks if float(s.quantite) > 0
        ]

    # ── Top articles vendus aujourd'hui (RESTAURANT seulement) ──
    top_articles = []
    lignes_today = LigneCommande.objects.filter(
        commande__created_at__date=today,
        commande__statut__in=['SERVIE', 'LIVREE', 'PRETE'],
    ).filter(
        Q(menu__isnull=False) | Q(produit__domaine__nom='RESTAURANT')
    ).values('menu__nom', 'produit__nom').annotate(
        qte=models.Sum('quantite'),
        total=models.Sum(models.F('quantite') * models.F('prix_unitaire')),
    ).order_by('-qte')[:5]
    for l in lignes_today:
        nom = l['menu__nom'] or l['produit__nom'] or 'Inconnu'
        if nom:
            top_articles.append({
                'nom': nom,
                'quantite': float(l['qte']),
                'total': float(l['total']),
            })

    # ── Dernières commandes ──
    dernieres_commandes = commandes_jour.order_by('-created_at')[:5]
    recentes = []
    for c in dernieres_commandes:
        recentes.append({
            'numero': c.numero,
            'type': c.get_type_commande_display(),
            'statut': c.get_statut_display(),
            'total': float(c.montant_total),
            'nb_articles': c.lignes.count(),
            'date': c.created_at.strftime('%H:%M'),
        })

    # ── Productions en cours ──
    nb_productions = Production.objects.filter(
        statut__in=['EN_ATTENTE', 'EN_COURS'],
        date_production=today,
    ).count()

    # ── File d'attente ──
    nb_file_attente = FileAttenteModel.objects.filter(statut='EN_ATTENTE').count()

    return JsonResponse({
        'ca_jour': ca_jour,
        'ca_semaine': ca_semaine,
        'ca_7jours': ca_7jours,
        'ventes_jour': nb_ventes_jour,
        'commandes_jour': nb_commandes_jour,
        'commandes_attente': commandes_attente,
        'commandes_preparation': commandes_preparation,
        'stock_alertes': stock_alertes,
        'top_articles': top_articles,
        'dernieres_commandes': recentes,
        'nb_productions': nb_productions,
        'nb_file_attente': nb_file_attente,
    })


@login_required
def api_tables_libres(request):
    """API pour récupérer les tables libres"""
    from ..models import TableModel
    
    tables = TableModel.objects.filter(statut='LIBRE')
    data = [
        {
            'numero': t.numero,
            'capacite': t.capacite,
            'zone': t.zone or 'Salle'
        }
        for t in tables
    ]
    return JsonResponse({'tables': data}, safe=False)


# ========== API POUR LES MENUS ==========

@login_required
def api_menus_pos(request):
    """API pour récupérer les menus pour le POS"""
    menus = MenuModel.objects.filter(
        visible_dans_pos=True, 
        actif=True
    ).order_by('ordre_affichage', 'nom')
    
    data = []
    for menu in menus:
        data.append({
            'id': menu.id,
            'nom': menu.nom,
            'prix': float(menu.prix_vente) if menu.prix_vente else 0,
            'description': menu.description or '',
            'image': menu.image.url if menu.image else None,
            'type_menu': menu.get_type_menu_display(),
            'code': menu.code,
            'temps_preparation': menu.get_temps_preparation_realiste() if hasattr(menu, 'get_temps_preparation_realiste') else 0
        })
    
    return JsonResponse({'success': True, 'menus': data})


@login_required
def api_menu_detail(request, menu_id):
    """API pour récupérer le détail d'un menu avec ses recettes"""
    menu = get_object_or_404(MenuModel, id=menu_id)
    lignes = menu.lignes.all().select_related('recette')
    
    recettes_data = []
    for ligne in lignes:
        recettes_data.append({
            'id': ligne.id,
            'recette_id': ligne.recette.id,
            'recette_nom': ligne.recette.nom,
            'quantite': ligne.quantite,
            'groupe': ligne.groupe,
            'type_ligne': ligne.type_ligne,
            'prix_supplement': float(ligne.prix_supplement) if ligne.prix_supplement else 0,
            'temps_preparation': ligne.recette.temps_preparation_minutes if hasattr(ligne.recette, 'temps_preparation_minutes') else 0
        })
    
    return JsonResponse({
        'success': True,
        'menu': {
            'id': menu.id,
            'nom': menu.nom,
            'code': menu.code,
            'prix': float(menu.prix_vente) if menu.prix_vente else 0,
            'description': menu.description or '',
            'image': menu.image.url if menu.image else None,
            'cout_revient': float(menu.get_cout_revient_total()),
            'temps_preparation': menu.get_temps_preparation_realiste() if hasattr(menu, 'get_temps_preparation_realiste') else 0
        },
        'recettes': recettes_data
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_save_menu_composition(request, menu_id):
    """API pour sauvegarder la composition d'un menu"""
    try:
        data = json.loads(request.body)
        menu = get_object_or_404(MenuModel, id=menu_id)
        lignes_data = data.get('lignes', [])
        
        # Supprimer les anciennes lignes
        LigneMenuModel.objects.filter(menu=menu).delete()
        
        # Créer les nouvelles lignes
        for ligne_data in lignes_data:
            recette = get_object_or_404(RecetteModel, id=ligne_data['recette_id'])
            
            LigneMenuModel.objects.create(
                id=str(uuid.uuid4()),
                menu=menu,
                recette=recette,
                groupe=ligne_data.get('groupe', 'PLAT'),
                type_ligne=ligne_data.get('type_ligne', 'FIXE'),
                quantite=ligne_data.get('quantite', 1),
                prix_supplement=Decimal(str(ligne_data.get('prix_supplement', 0)))
            )
        
        return JsonResponse({'success': True, 'message': 'Menu mis à jour'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ========== API POUR LES RECETTES ==========

@login_required
def api_recettes_disponibles(request):
    """API pour récupérer toutes les recettes disponibles"""
    recettes = RecetteModel.objects.filter(actif=True).values(
        'id', 'code', 'nom', 'type_recette', 'temps_preparation_minutes'
    )
    
    recettes_list = []
    for r in recettes:
        recette = RecetteModel.objects.get(id=r['id'])
        recettes_list.append({
            'id': r['id'],
            'code': r['code'],
            'nom': r['nom'],
            'type_recette': r['type_recette'],
            'temps_preparation_minutes': r['temps_preparation_minutes'],
            'cout_revient': float(recette.cout_revient({}))
        })
    
    return JsonResponse({'success': True, 'recettes': recettes_list})


@login_required
def api_recette_cout(request, recette_id):
    """API pour calculer le coût de revient d'une recette en temps réel"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    
    # Récupérer tous les produits actifs du domaine RESTAURANT
    produits = {p.id: p for p in Produit.objects.filter(actif=True, domaine__nom='RESTAURANT')}
    cout_total = recette.cout_revient(produits)
    
    details = []
    for ingredient in recette.ingredients.all():
        if ingredient.type_ingredient == 'DEDUIRE':
            produit = produits.get(ingredient.produit_id)
            prix = ingredient.cout_unitaire or (produit.prix_achat if produit else 0)
        else:
            prix = ingredient.cout_unitaire or 0
        
        cout = float(ingredient.quantite) * float(prix)
        details.append({
            'id': ingredient.id,
            'nom': ingredient.produit.nom if ingredient.produit else ingredient.nom,
            'quantite': float(ingredient.quantite),
            'unite': ingredient.unite,
            'cout': cout
        })
    
    return JsonResponse({
        'success': True,
        'cout_total': float(cout_total),
        'details': details
    })


@login_required
def api_recette_production(request, recette_id):
    """API pour vérifier la production possible"""
    from apps.stock.models import StockEntrepot, Entrepot
    
    recette = get_object_or_404(RecetteModel, id=recette_id)
    restaurant_entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    
    possible_min = None
    details = []
    
    for ingredient in recette.ingredients.filter(type_ingredient='DEDUIRE'):
        stock_qte = 0
        if restaurant_entrepot:
            stock = StockEntrepot.objects.filter(
                entrepot=restaurant_entrepot,
                produit=ingredient.produit
            ).first()
            stock_qte = float(stock.quantite) if stock else 0
        
        besoin = float(ingredient.quantite)
        possible = int(stock_qte // besoin) if besoin > 0 else 0
        
        details.append({
            'produit': ingredient.produit.nom,
            'stock': stock_qte,
            'besoin': besoin,
            'possible': possible,
            'unite': ingredient.unite
        })
        
        if possible_min is None or possible < possible_min:
            possible_min = possible
    
    return JsonResponse({
        'success': True,
        'production_possible': possible_min or 0,
        'details': details
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_save_recette_ingredients(request, recette_id):
    """API pour sauvegarder les ingrédients d'une recette"""
    try:
        data = json.loads(request.body)
        recette = get_object_or_404(RecetteModel, id=recette_id)
        ingredients_data = data.get('ingredients', [])
        
        # Supprimer les anciens ingrédients
        IngredientModel.objects.filter(recette=recette).delete()
        
        # Créer les nouveaux
        for ing_data in ingredients_data:
            quantite = Decimal(str(ing_data.get('quantite', 0)))
            cout_unitaire = None
            if ing_data.get('cout_unitaire'):
                cout_unitaire = Decimal(str(ing_data.get('cout_unitaire')))
            
            IngredientModel.objects.create(
                id=str(uuid.uuid4())[:8],
                recette=recette,
                type_ingredient=ing_data.get('type_ingredient', 'DEDUIRE'),
                produit_id=ing_data.get('produit_id') if ing_data.get('produit_id') else None,
                nom=ing_data.get('nom', ''),
                quantite=quantite,
                unite=ing_data.get('unite', 'piece'),
                cout_unitaire=cout_unitaire
            )
        
        return JsonResponse({'success': True, 'message': 'Ingrédients sauvegardés'})
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_save_recette_etapes(request, recette_id):
    """API pour sauvegarder les étapes d'une recette"""
    try:
        data = json.loads(request.body)
        recette = get_object_or_404(RecetteModel, id=recette_id)
        etapes_data = data.get('etapes', [])
        
        # Supprimer les anciennes étapes
        from ..models import EtapePreparationModel
        EtapePreparationModel.objects.filter(recette=recette).delete()
        
        # Créer les nouvelles
        for etape_data in etapes_data:
            EtapePreparationModel.objects.create(
                id=str(uuid.uuid4())[:8],
                recette=recette,
                ordre=int(etape_data.get('ordre', 0)),
                instruction=etape_data.get('instruction', ''),
                duree_minutes=int(etape_data.get('duree_minutes')) if etape_data.get('duree_minutes') else None
            )
        
        return JsonResponse({'success': True, 'message': 'Étapes sauvegardées'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_get_recette_ingredients(request, recette_id):
    """API pour récupérer les ingrédients d'une recette"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    ingredients = recette.ingredients.all()
    
    data = []
    for ing in ingredients:
        data.append({
            'id': ing.id,
            'type_ingredient': ing.type_ingredient,
            'produit_id': ing.produit_id,
            'produit_nom': ing.produit.nom if ing.produit else '',
            'nom': ing.nom,
            'nom_display': ing.produit.nom if ing.produit else (ing.nom or 'Ingrédient'),
            'quantite': float(ing.quantite),
            'unite': ing.unite,
            'cout_unitaire': float(ing.cout_unitaire) if ing.cout_unitaire else None
        })
    
    return JsonResponse({'success': True, 'ingredients': data})


@login_required
def api_get_recette_etapes(request, recette_id):
    """API pour récupérer les étapes d'une recette"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    etapes = recette.etapes.all().order_by('ordre')
    
    data = []
    for etape in etapes:
        data.append({
            'id': etape.id,
            'ordre': etape.ordre,
            'instruction': etape.instruction,
            'duree_minutes': etape.duree_minutes
        })
    
    return JsonResponse({'success': True, 'etapes': data})




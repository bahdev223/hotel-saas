# apps/restaurant/views/recettes.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
import json
import uuid

from ..models import RecetteModel, IngredientModel, EtapePreparationModel
from apps.stock.models import Produit, StockEntrepot, Entrepot


# Types pour le template
TYPE_RECETTE_CHOICES = [
    ('PLAT', 'Plat'),
    ('BOISSON', 'Boisson'),
    ('DESSERT', 'Dessert'),
    ('COCKTAIL', 'Cocktail'),
    ('PETIT_DEJEUNER', 'Petit-déjeuner'),
    ('ACCOMPAGNEMENT', 'Accompagnement'),
]

UNITE_INGREDIENT_CHOICES = [
    ('kg', 'Kilogramme'),
    ('g', 'Gramme'),
    ('l', 'Litre'),
    ('ml', 'Millilitre'),
    ('piece', 'Pièce'),
    ('cuillere_cafe', 'Cuillère à café'),
    ('cuillere_soupe', 'Cuillère à soupe'),
    ('verre', 'Verre'),
    ('bouteille', 'Bouteille'),
    ('pincee', 'Pincée'),
    ('morceau', 'Morceau'),
    ('louche', 'Louche'),
    ('poignee', 'Poignée'),
    ('unite', 'Unité'),
]


@login_required
@login_required
def api_liste_recettes(request):
    """API JSON - Liste des recettes"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            nom = data.get('nom', 'Nouvelle recette')
            type_recette = data.get('type_recette', 'PLAT')
            last = RecetteModel.objects.filter(actif=True).order_by('-created_at').first()
            n = 1
            if last and last.code and last.code.startswith('R'):
                try: n = int(last.code[1:]) + 1
                except: pass
            code = f'R{n:04d}'
            recette = RecetteModel.objects.create(
                id=str(uuid.uuid4())[:8],
                code=code,
                nom=nom,
                type_recette=type_recette,
            )
            return JsonResponse({'success': True, 'recette': {
                'id': recette.id,
                'code': recette.code,
                'nom': recette.nom,
                'type_recette': recette.type_recette,
                'type_label': recette.get_type_recette_display(),
                'prix_vente': 0,
                'ingredients': [],
                'nb_ingredients': 0,
            }})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)}, status=400)

    recettes = RecetteModel.objects.filter(actif=True).order_by('nom')
    data = []
    for r in recettes:
        ingredients = [
            {
                'id': ing.id,
                'produit_id': ing.produit_id,
                'produit_nom': ing.produit.nom if ing.produit else ing.nom,
                'quantite': float(ing.quantite) if ing.quantite else 0,
                'unite': ing.unite,
            }
            for ing in r.ingredients.filter(type_ingredient='DEDUIRE')
        ]
        data.append({
            'id': r.id,
            'code': r.code,
            'nom': r.nom,
            'type_recette': r.type_recette,
            'type_label': r.get_type_recette_display(),
            'prix_vente': float(r.prix_vente) if r.prix_vente else 0,
            'temps_preparation': r.temps_preparation_minutes,
            'ingredients': ingredients,
            'nb_ingredients': len(ingredients),
        })
    return JsonResponse({'success': True, 'recettes': data})


@login_required
def api_recette_menus(request, recette_id):
    """Menus liés à une recette"""
    from ..models.menu import LigneMenuModel, MenuModel
    lignes = LigneMenuModel.objects.filter(recette_id=recette_id).select_related('menu')
    menus = [{'id': l.menu.id, 'nom': l.menu.nom, 'code': l.menu.code} for l in lignes]
    return JsonResponse({'success': True, 'menus': menus})


@login_required
def api_recette_modifier(request, recette_id):
    """API modifier champs simples d'une recette"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'}, status=405)
    recette = get_object_or_404(RecetteModel, id=recette_id)
    data = json.loads(request.body)
    for field in ['nom', 'type_recette', 'prix_vente', 'description', 'temps_preparation_minutes']:
        if field in data:
            setattr(recette, field, data[field])
    recette.save()
    return JsonResponse({'success': True})


def recettes_liste(request):
    """Liste des recettes / menu"""
    type_recette = request.GET.get('type')
    search = request.GET.get('search')
    visible = request.GET.get('visible')
    
    recettes = RecetteModel.objects.filter(actif=True)
    
    if type_recette:
        recettes = recettes.filter(type_recette=type_recette)
    if search:
        recettes = recettes.filter(
            Q(nom__icontains=search) | 
            Q(code__icontains=search)
        )
    if visible == 'oui':
        recettes = recettes.filter(visible_dans_pos=True)
    elif visible == 'non':
        recettes = recettes.filter(visible_dans_pos=False)
    
    context = {
        'recettes': recettes,
        'filtre_type': type_recette,
        'filtre_visible': visible,
        'search': search,
        'types_recette': TYPE_RECETTE_CHOICES,
        'unites_ingredient': UNITE_INGREDIENT_CHOICES,
    }
    return render(request, 'restaurant/recettes/liste.html', context)


@login_required
def recette_detail(request, recette_id):
    """Détail d'une recette avec gestion des quantités optionnelles"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    ingredients = recette.ingredients.all()
    etapes = recette.etapes.all()
    
    # Récupérer les produits RESTAURANT pour le modal
    produits_list = Produit.objects.filter(actif=True, domaine__nom='RESTAURANT').order_by('nom')
    
    # Récupérer les produits avec leurs prix
    produits_dict = {p.id: p for p in produits_list}
    
    # Récupérer l'entrepôt RESTAURANT pour le stock
    restaurant_entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    
    cout_total = 0
    production_possible = []
    
    for ingredient in ingredients:
        produit = produits_dict.get(ingredient.produit_id)
        prix = ingredient.cout_unitaire or (produit.prix_achat if produit else 0)
        
        # Gestion des quantités optionnelles
        quantite = float(ingredient.quantite) if ingredient.quantite else 1
        cout = quantite * float(prix)
        cout_total += cout
        
        # Stock dans l'entrepôt RESTAURANT (uniquement si quantité précise)
        stock_qte = 0
        besoin = 0
        possible = 999
        
        if restaurant_entrepot and produit and ingredient.quantite and ingredient.quantite > 0:
            stock = StockEntrepot.objects.filter(
                entrepot=restaurant_entrepot, 
                produit=produit
            ).first()
            stock_qte = float(stock.quantite) if stock else 0
            besoin = float(ingredient.quantite)
            possible = int(stock_qte // besoin) if besoin > 0 else 0
        
        production_possible.append({
            'ingredient': ingredient,
            'stock': stock_qte,
            'besoin': besoin,
            'possible': possible,
            'quantite_approximative': not ingredient.quantite or ingredient.quantite <= 0
        })
    
    marge = float(recette.prix_vente) - cout_total if recette.prix_vente else 0
    marge_pourcentage = (marge / float(recette.prix_vente) * 100) if recette.prix_vente and recette.prix_vente > 0 else 0
    
    # Filtrer les possibilités réelles
    possibilites_reelles = [p['possible'] for p in production_possible if p['besoin'] > 0]
    nb_portions = min(possibilites_reelles) if possibilites_reelles else 0
    
    context = {
        'recette': recette,
        'ingredients': ingredients,
        'etapes': etapes,
        'produits': produits_list,
        'cout_total': cout_total,
        'marge': marge,
        'marge_pourcentage': marge_pourcentage,
        'production_possible': production_possible,
        'nb_portions': nb_portions,
        'unites_ingredient': UNITE_INGREDIENT_CHOICES,
    }
    return render(request, 'restaurant/recettes/detail.html', context)


@login_required
def recette_ajouter(request):
    """Ajouter une nouvelle recette"""
    if request.method == 'POST':
        try:
            code = request.POST.get('code')
            nom = request.POST.get('nom')
            type_recette = request.POST.get('type_recette')
            
            if not code:
                raise ValueError("Le code est obligatoire")
            if not nom:
                raise ValueError("Le nom est obligatoire")
            if not type_recette:
                raise ValueError("Le type de recette est obligatoire")
            
            recette = RecetteModel.objects.create(
                id=str(uuid.uuid4())[:8],
                code=code,
                nom=nom,
                type_recette=type_recette,
                description=request.POST.get('description', ''),
                prix_vente=float(request.POST.get('prix_vente')) if request.POST.get('prix_vente') else None,
                temps_preparation_minutes=int(request.POST.get('temps_preparation', 0)),
                visible_dans_pos=request.POST.get('visible_dans_pos') == 'on',
                ordre_affichage=int(request.POST.get('ordre_affichage', 0)),
                notes=request.POST.get('notes', '')
            )
            messages.success(request, f'Recette "{recette.nom}" créée')
            return redirect('restaurant:recette_modifier', recette_id=recette.id)
            
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    context = {
        'types_recette': TYPE_RECETTE_CHOICES,
        'unites_ingredient': UNITE_INGREDIENT_CHOICES,
    }
    return render(request, 'restaurant/recettes/ajouter.html', context)


@login_required
def recette_modifier(request, recette_id):
    """Modifier une recette (uniquement les infos de base)"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    
    if request.method == 'POST':
        recette.nom = request.POST.get('nom')
        recette.type_recette = request.POST.get('type_recette')
        recette.description = request.POST.get('description', '')
        recette.prix_vente = float(request.POST.get('prix_vente')) if request.POST.get('prix_vente') else None
        recette.temps_preparation_minutes = int(request.POST.get('temps_preparation', 0))
        recette.visible_dans_pos = request.POST.get('visible_dans_pos') == 'on'
        recette.ordre_affichage = int(request.POST.get('ordre_affichage', 0))
        recette.notes = request.POST.get('notes', '')
        recette.save()
        messages.success(request, 'Recette mise à jour')
        return redirect('restaurant:recette_detail', recette_id=recette.id)
    
    context = {
        'recette': recette,
        'types_recette': TYPE_RECETTE_CHOICES,
        'unites_ingredient': UNITE_INGREDIENT_CHOICES,
    }
    return render(request, 'restaurant/recettes/modifier.html', context)


@login_required
def recette_supprimer(request, recette_id):
    """Supprimer une recette"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    if request.method == 'POST':
        recette.delete()
        messages.success(request, 'Recette supprimée')
        return redirect('restaurant:recettes_liste')
    return render(request, 'restaurant/recettes/supprimer.html', {'recette': recette})


# Ajoute ces fonctions si elles n'existent pas
@login_required
def recette_dupliquer(request, recette_id):
    """Dupliquer une recette"""
    recette_originale = get_object_or_404(RecetteModel, id=recette_id)
    
    if request.method == 'POST':
        nouvelle_recette = RecetteModel.objects.create(
            id=str(uuid.uuid4())[:8],
            code=request.POST.get('nouveau_code'),
            nom=request.POST.get('nouveau_nom'),
            type_recette=recette_originale.type_recette,
            description=recette_originale.description,
            prix_vente=recette_originale.prix_vente,
            temps_preparation_minutes=recette_originale.temps_preparation_minutes,
            visible_dans_pos=recette_originale.visible_dans_pos,
            ordre_affichage=recette_originale.ordre_affichage,
            notes=recette_originale.notes
        )
        
        for ingredient in recette_originale.ingredients.all():
            IngredientModel.objects.create(
                id=str(uuid.uuid4())[:8],
                recette=nouvelle_recette,
                produit_id=ingredient.produit_id,
                quantite=ingredient.quantite,
                unite=ingredient.unite,
                cout_unitaire=ingredient.cout_unitaire
            )
        
        for etape in recette_originale.etapes.all():
            EtapePreparationModel.objects.create(
                id=str(uuid.uuid4())[:8],
                recette=nouvelle_recette,
                ordre=etape.ordre,
                instruction=etape.instruction,
                duree_minutes=etape.duree_minutes
            )
        
        messages.success(request, 'Recette dupliquée')
        return redirect('restaurant:recette_detail', recette_id=nouvelle_recette.id)
    
    return render(request, 'restaurant/recettes/dupliquer.html', {'recette': recette_originale})


@login_required
def calcul_cout(request, recette_id):
    """Calculer le coût de revient"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    
    produits = {p.id: p for p in Produit.objects.filter(actif=True, domaine__nom='RESTAURANT')}
    cout_total = 0
    details = []
    
    for ingredient in recette.ingredients.all():
        produit = produits.get(ingredient.produit_id)
        prix = ingredient.cout_unitaire or (produit.prix_achat if produit else 0)
        quantite = float(ingredient.quantite) if ingredient.quantite else 1
        cout = quantite * float(prix)
        cout_total += cout
        details.append({
            'produit_nom': produit.nom if produit else str(ingredient.produit_id),
            'quantite': quantite,
            'quantite_approximative': not ingredient.quantite,
            'unite': ingredient.unite,
            'prix': float(prix),
            'cout': cout
        })
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'cout_total': cout_total, 'details': details})
    
    return render(request, 'restaurant/recettes/cout.html', {
        'recette': recette,
        'cout_total': cout_total,
        'details': details
    })


@login_required
def production_possible_api(request, recette_id):
    """API production possible avec stock réel (uniquement ingrédients mesurables)"""
    recette = get_object_or_404(RecetteModel, id=recette_id)
    restaurant_entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    
    possible_min = None
    details = []
    
    for ingredient in recette.ingredients.filter(type_ingredient='DEDUIRE'):
        if not ingredient.quantite or ingredient.quantite <= 0:
            continue
            
        produit = ingredient.produit
        stock_qte = 0
        
        if restaurant_entrepot and produit:
            stock = StockEntrepot.objects.filter(
                entrepot=restaurant_entrepot, 
                produit=produit
            ).first()
            stock_qte = float(stock.quantite) if stock else 0
        
        besoin = float(ingredient.quantite)
        possible = int(stock_qte // besoin) if besoin > 0 else 0
        
        details.append({
            'produit': produit.nom,
            'stock': stock_qte,
            'besoin': besoin,
            'possible': possible,
            'unite': ingredient.unite
        })
        
        if possible_min is None or possible < possible_min:
            possible_min = possible
    
    return JsonResponse({
        'production_possible': possible_min or 0,
        'details': details
    })


@login_required
def get_menu_pos_api(request):
    """API pour le POS - récupère le menu"""
    recettes = RecetteModel.objects.filter(visible_dans_pos=True, actif=True).order_by('ordre_affichage', 'nom')
    
    data = []
    for recette in recettes:
        data.append({
            'id': recette.id,
            'nom': recette.nom,
            'prix': float(recette.prix_vente) if recette.prix_vente else 0,
            'type': recette.type_recette,
            'description': recette.description or '',
            'image': recette.image.url if recette.image else None,
            'temps_preparation': recette.temps_preparation_minutes
        })
    
    return JsonResponse({'menu': data, 'success': True})


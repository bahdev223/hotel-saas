# apps/restaurant/views/produits.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import json
import uuid

from apps.stock.models import Produit, StockEntrepot, Entrepot


UNITE_CHOICES = [
    ('piece', 'Pièce'),
    ('kg', 'Kilogramme'),
    ('g', 'Gramme'),
    ('l', 'Litre'),
    ('cl', 'Centilitre'),
    ('botte', 'Botte'),
    ('sachet', 'Sachet'),
    ('boite', 'Boîte'),
    ('caisse', 'Caisse'),
]

RAISON_CHOICES = [
    ('ACHAT', 'Achat fournisseur'),
    ('TRANSFERT', 'Transfert'),
    ('CASSE', 'Casse / Perte'),
    ('INVENTAIRE', 'Inventaire'),
    ('CONSOMMATION', 'Consommation'),
]


def get_restaurant_entrepot():
    """Récupère ou crée l'entrepôt RESTAURANT"""
    entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    if not entrepot:
        entrepot = Entrepot.objects.create(
            code='RESTAURANT',
            nom='RESTAURANT',
            type_entrepot='RESTAURANT',
            actif=True
        )
    return entrepot


@login_required
def produits_stock(request):
    """Page de consultation du stock de l'entrepôt RESTAURANT"""
    restaurant_entrepot = get_restaurant_entrepot()
    context = { 'entrepot_nom': restaurant_entrepot.nom }
    return render(request, 'restaurant/produits/liste.html', context)


@login_required
def entree_stock(request, produit_id):
    """Ajouter du stock dans l'entrepôt RESTAURANT"""
    produit = get_object_or_404(Produit, id=produit_id)
    restaurant_entrepot = get_restaurant_entrepot()
    
    if request.method == 'POST':
        try:
            quantite = Decimal(request.POST.get('quantite', 0))
            raison = request.POST.get('raison', '')
            reference = request.POST.get('reference', '')
            
            # Mettre à jour le stock dans l'entrepôt RESTAURANT
            stock, created = StockEntrepot.objects.get_or_create(
                entrepot=restaurant_entrepot,
                produit=produit,
                defaults={'quantite': 0}
            )
            stock.quantite += quantite
            stock.save()
            
            # Créer le mouvement
            MouvementStock.objects.create(
                produit=produit,
                type_mouvement='ENTREE',
                quantite=quantite,
                entrepot_dest=restaurant_entrepot,
                reference=reference,
                utilisateur=request.user.username,
                raison=f"Entrée stock restaurant: {raison}"
            )
            
            messages.success(request, f'{quantite} {produit.unite_base} ajoutés au stock du restaurant')
            return redirect('restaurant:produits_stock')
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'produit': produit,
        'raisons': RAISON_CHOICES,
    }
    return render(request, 'restaurant/produits/entree.html', context)


@login_required
def mouvement_stock(request, produit_id):
    """Historique des mouvements de stock pour un produit"""
    produit = get_object_or_404(Produit, id=produit_id)
    
    mouvements = MouvementStock.objects.filter(produit=produit).order_by('-date_mouvement')[:50]
    
    context = {
        'produit': produit,
        'mouvements': mouvements,
    }
    return render(request, 'restaurant/produits/mouvements.html', context)


@login_required
def ajouter_produit(request):
    """Ajouter un nouveau produit"""
    if request.method == 'POST':
        try:
            code = request.POST.get('code') or f"PRD-{uuid.uuid4().hex[:6].upper()}"
            
            produit = Produit.objects.create(
                code=code,
                nom=request.POST.get('nom'),
                unite_base=request.POST.get('unite_base', 'piece'),
                prix_achat=Decimal(request.POST.get('prix_achat', 0)),
                prix_vente=Decimal(request.POST.get('prix_vente', 0)),
                seuil_alerte=Decimal(request.POST.get('seuil_alerte', 5)),
                description=request.POST.get('description', ''),
                actif=True
            )
            
            messages.success(request, f'Produit {produit.nom} ajouté')
            return redirect('restaurant:produits_stock')
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'unites': UNITE_CHOICES,
    }
    return render(request, 'restaurant/produits/ajouter.html', context)


@login_required
def modifier_produit(request, produit_id):
    """Modifier un produit"""
    produit = get_object_or_404(Produit, id=produit_id)
    
    if request.method == 'POST':
        try:
            produit.nom = request.POST.get('nom')
            produit.unite_base = request.POST.get('unite_base')
            produit.prix_achat = Decimal(request.POST.get('prix_achat', 0))
            produit.prix_vente = Decimal(request.POST.get('prix_vente', 0))
            produit.seuil_alerte = Decimal(request.POST.get('seuil_alerte', 5))
            produit.description = request.POST.get('description', '')
            produit.save()
            
            messages.success(request, f'Produit {produit.nom} modifié')
            return redirect('restaurant:produits_stock')
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'produit': produit,
        'unites': UNITE_CHOICES,
    }
    return render(request, 'restaurant/produits/modifier.html', context)


@login_required
def transfert_central_restaurant(request, produit_id):
    """Transférer un produit du stock CENTRAL vers RESTAURANT"""
    from apps.stock.services.transfert_service import TransfertService
    
    produit = get_object_or_404(Produit, id=produit_id)
    
    if request.method == 'POST':
        try:
            quantite = Decimal(request.POST.get('quantite', 0))
            
            mouvement = TransfertService.transfert_central_vers_restaurant(
                produit_id=produit_id,
                quantite=quantite,
                utilisateur=request.user.username,
                reference=request.POST.get('reference', ''),
                notes=request.POST.get('notes', '')
            )
            
            messages.success(request, f'{quantite} {produit.unite_base} transférés vers le restaurant')
            return redirect('restaurant:produits_stock')
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'produit': produit,
    }
    return render(request, 'restaurant/produits/transfert.html', context)


@login_required
@require_http_methods(["GET"])
def api_liste_produits_stock(request):
    """Liste des produits du stock restaurant uniquement"""
    restaurant_entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    if not restaurant_entrepot:
        return JsonResponse({'success': True, 'produits': []})
    stocks = StockEntrepot.objects.filter(
        entrepot=restaurant_entrepot,
        produit__actif=True,
        produit__domaine__nom='RESTAURANT'
    ).select_related('produit', 'produit__categorie', 'produit__domaine')
    data = []
    for s in stocks:
        p = s.produit
        qte = float(s.quantite)
        data.append({
            'id': p.id, 'code': p.code, 'nom': p.nom,
            'type_article': p.type_article,
            'categorie': p.categorie.nom if p.categorie else '',
            'categorie_id': p.categorie_id,
            'domaine': p.domaine.nom if p.domaine else '',
            'domaine_id': p.domaine_id,
            'prix_vente': float(p.prix_vente), 'prix_achat': float(p.prix_achat),
            'unite_base': p.unite_base,
            'quantite_stock': qte, 'seuil_alerte': float(p.seuil_alerte),
            'est_en_rupture': qte <= 0, 'est_en_alerte': 0 < qte <= float(p.seuil_alerte),
        })
    return JsonResponse({'success': True, 'produits': data})


# ─── API JSON ───────────────────────────────────────────────────────────────


@login_required
@require_http_methods(["GET"])
def api_produit_infos(request, produit_id):
    """Détail d'un produit avec son stock restaurant"""
    produit = get_object_or_404(Produit, id=produit_id)
    entrepot = get_restaurant_entrepot()
    stock = StockEntrepot.objects.filter(entrepot=entrepot, produit=produit).first()
    qte = float(stock.quantite) if stock else 0
    return JsonResponse({
        'success': True,
        'produit': {
            'id': produit.id, 'code': produit.code, 'nom': produit.nom,
            'prix_achat': float(produit.prix_achat), 'prix_vente': float(produit.prix_vente),
            'unite_base': produit.unite_base,
            'seuil_alerte': float(produit.seuil_alerte),
            'quantite_stock': qte, 'description': produit.description or '',
            'categorie': produit.categorie.nom if produit.categorie else '',
            'categorie_id': produit.categorie_id,
            'image': produit.image.url if produit.image else None,
        }
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_ajouter_produit(request):
    """Ajouter un produit via JSON"""
    try:
        data = json.loads(request.body) if request.body else request.POST.dict()
        nom = data.get('nom', '').strip()
        if not nom:
            return JsonResponse({'success': False, 'error': 'Nom requis'})
        produit = Produit.objects.create(
            code=data.get('code') or f"PRD-{uuid.uuid4().hex[:6].upper()}",
            nom=nom,
            type_article=data.get('type_article', 'MARCHANDISE'),
            unite_base=data.get('unite_base', 'piece'),
            prix_achat=Decimal(str(data.get('prix_achat', 0))),
            prix_vente=Decimal(str(data.get('prix_vente', 0))),
            seuil_alerte=Decimal(str(data.get('seuil_alerte', 5))),
            description=data.get('description', ''),
            actif=True,
        )
        return JsonResponse({'success': True, 'id': produit.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_modifier_produit(request, produit_id):
    """Modifier un produit via JSON"""
    try:
        data = json.loads(request.body) if request.body else request.POST.dict()
        produit = get_object_or_404(Produit, id=produit_id)
        produit.nom = data.get('nom', produit.nom)
        produit.type_article = data.get('type_article', produit.type_article)
        produit.unite_base = data.get('unite_base', produit.unite_base)
        produit.prix_achat = Decimal(str(data.get('prix_achat', produit.prix_achat)))
        produit.prix_vente = Decimal(str(data.get('prix_vente', produit.prix_vente)))
        produit.seuil_alerte = Decimal(str(data.get('seuil_alerte', produit.seuil_alerte)))
        produit.description = data.get('description', produit.description)
        produit.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_entree_stock(request, produit_id):
    """Entrée de stock via JSON"""
    try:
        data = json.loads(request.body) if request.body else request.POST.dict()
        produit = get_object_or_404(Produit, id=produit_id)
        quantite = Decimal(str(data.get('quantite', 0)))
        if quantite <= 0:
            return JsonResponse({'success': False, 'error': 'Quantité invalide'})
        raison = data.get('raison', 'ACHAT')
        reference = data.get('reference', '')
        restaurant_entrepot = get_restaurant_entrepot()
        stock, _ = StockEntrepot.objects.get_or_create(entrepot=restaurant_entrepot, produit=produit, defaults={'quantite': 0})
        stock.quantite += quantite
        stock.save()
        MouvementStock.objects.create(
            produit=produit, type_mouvement='ENTREE', quantite=quantite,
            entrepot_dest=restaurant_entrepot, reference=reference,
            utilisateur=request.user.username, raison=f"Entrée stock restaurant: {raison}"
        )
        return JsonResponse({'success': True, 'nouveau_stock': float(stock.quantite)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def supprimer_produit(request, produit_id):
    """Supprimer un produit (soft delete)"""
    produit = get_object_or_404(Produit, id=produit_id)
    if request.method == 'POST':
        produit.actif = False
        produit.save()
        messages.success(request, f'Produit {produit.nom} supprimé')
        return redirect('restaurant:produits_stock')
    return redirect('restaurant:produits_stock')


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_supprimer_produit(request, produit_id):
    """Supprimer un produit via JSON (soft delete)"""
    try:
        produit = get_object_or_404(Produit, id=produit_id)
        produit.actif = False
        produit.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


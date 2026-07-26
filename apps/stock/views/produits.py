# apps/stock/views/produits.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q, OuterRef, Subquery, Value, F
from django.db.models.functions import Coalesce
from django.db import models
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal
import json
import uuid

from ..models import Produit, CategorieProduit, SousUnite, StockEntrepot, Entrepot, Domaine, UniteMesure
from ..constants import ALLOWED_STOCK_GROUPS



@login_required
def liste_produits(request):
    """Catalogue produits : page dédiée avec recherche et filtres."""
    from django.core.paginator import Paginator
    from django.db.models import Q, Sum, F
    from ..models import StockEntrepot

    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "Accès refusé.")
        return redirect('admin:index')

    produits = Produit.objects.select_related('categorie', 'domaine').all()

    recherche = request.GET.get('q', '').strip()
    categorie_id = request.GET.get('categorie', '')
    domaine_id = request.GET.get('domaine', '')
    type_article = request.GET.get('type_article', '')
    etat_stock = request.GET.get('etat', '')
    actif = request.GET.get('actif', '1')

    if recherche:
        produits = produits.filter(
            Q(nom__icontains=recherche) | Q(code__icontains=recherche) | Q(code_barre__icontains=recherche)
        )
    if categorie_id:
        produits = produits.filter(categorie_id=categorie_id)
    if domaine_id:
        produits = produits.filter(domaine_id=domaine_id)
    if type_article:
        produits = produits.filter(type_article=type_article)
    if actif in ('0', '1'):
        produits = produits.filter(actif=(actif == '1'))

    produits = produits.annotate(stock_total=Coalesce(Sum('stocks_entrepots__quantite'), Value(Decimal('0'))))

    if etat_stock == 'rupture':
        produits = produits.filter(stock_total__lte=0)
    elif etat_stock == 'alerte':
        produits = produits.filter(stock_total__gt=0, stock_total__lte=F('seuil_alerte'))
    elif etat_stock == 'ok':
        produits = produits.filter(stock_total__gt=F('seuil_alerte'))

    produits = produits.order_by('nom')
    paginator = Paginator(produits, 40)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'produits': page,
        'total_resultats': paginator.count,
        'categories': CategorieProduit.objects.filter(actif=True).order_by('nom'),
        'domaines': Domaine.objects.filter(actif=True).order_by('ordre', 'nom'),
        'types_article': Produit.TYPE_ARTICLE_CHOICES,
        'f': {
            'q': recherche, 'categorie': categorie_id, 'domaine': domaine_id,
            'type_article': type_article, 'etat': etat_stock, 'actif': actif,
        },
    }
    return render(request, 'stock/produits/liste.html', context)


@login_required
def ajouter_produit(request):
    """Formulaire d'ajout de produit"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    context = {
        'categories': CategorieProduit.objects.filter(actif=True),
        'domaines': Domaine.objects.filter(actif=True).order_by('ordre', 'nom'),
    }
    return render(request, 'stock/produits/ajouter.html', context)


@csrf_exempt
def api_ajouter_produit(request):
    """API pour ajouter un produit avec image et stock initial"""
    
    # VÃ©rifier les droits
    if request.user.is_authenticated:
        user_groups = request.user.groups.values_list('name', flat=True)
        if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
            return JsonResponse({'success': False, 'error': 'â›” AccÃ¨s refusÃ©'}, status=403)
    else:
        return JsonResponse({'success': False, 'error': 'Non authentifiÃ©'}, status=401)
    
    if request.method == 'POST':
        try:
            # VÃ©rifier si c'est un FormData (avec image) ou JSON
            if request.content_type and 'multipart' in request.content_type:
                # Formulaire multipart (avec image)
                produit_data = {
                    'nom': request.POST.get('nom'),
                    'categorie': request.POST.get('categorie'),
                    'unite_base': request.POST.get('unite_base', 'piece'),
                    'prix_achat': Decimal(request.POST.get('prix_achat', 0)),
                    'prix_vente': Decimal(request.POST.get('prix_vente', 0)),
                    'seuil_alerte': Decimal(request.POST.get('seuil_alerte', 5)),
                    'quantite_initiale': Decimal(request.POST.get('quantite_initiale', 0)),
                    'description': request.POST.get('description', '')
                }
                sous_unites_data = json.loads(request.POST.get('sous_unites', '[]'))
                image = request.FILES.get('image')
            else:
                # JSON (sans image)
                data = json.loads(request.body)
                produit_data = data.get('produit', {})
                sous_unites_data = data.get('sous_unites', [])
                domaines_ids = data.get('domaines', [])
                image = None
            
            quantite_initiale = Decimal(produit_data.get('quantite_initiale', 0))
            
            code = produit_data.get('code')
            if not code:
                code = f"PRD-{uuid.uuid4().hex[:6].upper()}"
            
            # 1. CrÃ©er le produit
            produit = Produit.objects.create(
                code=code,
                nom=produit_data.get('nom'),
                categorie_id=produit_data.get('categorie') or None,
                unite_mesure=UniteMesure.get_or_create_by_symbole(produit_data.get('unite_base', 'piece')),
                prix_achat=Decimal(produit_data.get('prix_achat', 0)),
                prix_vente=Decimal(produit_data.get('prix_vente', 0)),
                seuil_alerte=Decimal(produit_data.get('seuil_alerte', 5)),
                budget_mensuel=Decimal(produit_data.get('budget_mensuel', 0)),
                description=produit_data.get('description', ''),
                image=image,
                actif=True
            )
            
            # 2. CrÃ©er les sous-unitÃ©s
            for su in sous_unites_data:
                SousUnite.objects.create(
                    produit=produit,
                    nom=su.get('nom'),
                    facteur=Decimal(su.get('facteur', 1)),
                    prix=Decimal(su.get('prix')) if su.get('prix') else None,
                    actif=True
                )
            
            # 3. Ajouter le domaine
            domaine_id = request.POST.get('domaine') or (data.get('domaine') if not (request.content_type and 'multipart' in request.content_type) else None)
            if domaine_id:
                produit.domaine_id = domaine_id
                produit.save(update_fields=['domaine_id'])
            
            return JsonResponse({'success': True, 'produit_id': produit.id, 'code': produit.code})
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
def modifier_produit(request, produit_id):
    """Redirige vers le dÃ©tail du produit (Ã©dition via modal brasserie)"""
    produit = get_object_or_404(Produit, id=produit_id)
    messages.info(request, "Utilisez le bouton Modifier dans la liste des produits brasserie.")
    return redirect('stock:detail_produit', produit_id=produit.id)


@login_required
def supprimer_produit(request, produit_id):
    """Supprimer un produit (soft delete)"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    produit = get_object_or_404(Produit, id=produit_id)
    
    if request.method == 'POST':
        produit.actif = False
        produit.save()
        messages.success(request, f'Produit {produit.nom} supprimÃ©')
        return redirect('stock:liste_produits')
    
    context = {'produit': produit}
    return render(request, 'stock/produits/supprimer.html', context)


@login_required
def detail_produit(request, produit_id):
    """DÃ©tail d'un produit"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        messages.error(request, "â›” AccÃ¨s refusÃ©. Vous n'Ãªtes pas autorisÃ© Ã  accÃ©der Ã  cette page.")
        return redirect('admin:index')
    
    produit = get_object_or_404(Produit, id=produit_id)

    central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
    stock_central = StockEntrepot.objects.filter(entrepot=central, produit=produit).first() if central else None
    stock_reel = stock_central.quantite if stock_central else 0

    # Stock détaillé par entrepôt : où se trouve physiquement ce produit
    stocks_par_entrepot = list(
        StockEntrepot.objects.filter(produit=produit).select_related('entrepot').order_by('-quantite')
    )
    stock_total = Decimal('0')
    valeur_totale = Decimal('0')
    for s in stocks_par_entrepot:
        cout = s.prix_achat or produit.prix_achat or Decimal('0')
        s.valeur_ligne = s.quantite * cout  # attribut de rendu, pas persisté
        s.cout_unitaire = cout
        stock_total += s.quantite
        valeur_totale += s.valeur_ligne

    # Historique complet des mouvements, filtrable (type, entrepôt, période)
    mouvements = produit.mouvements.select_related(
        'entrepot_source', 'entrepot_dest', 'source_operation',
    ).order_by('-date_mouvement')

    f_type = request.GET.get('type', '')
    f_entrepot = request.GET.get('entrepot', '')
    f_debut = request.GET.get('debut', '')
    f_fin = request.GET.get('fin', '')

    if f_type:
        mouvements = mouvements.filter(type_mouvement=f_type)
    if f_entrepot:
        mouvements = mouvements.filter(
            Q(entrepot_source_id=f_entrepot) | Q(entrepot_dest_id=f_entrepot)
        )
    if f_debut:
        mouvements = mouvements.filter(date_mouvement__date__gte=f_debut)
    if f_fin:
        mouvements = mouvements.filter(date_mouvement__date__lte=f_fin)

    total_mouvements = mouvements.count()
    paginator = Paginator(mouvements, 50)
    mouvements_page = paginator.get_page(request.GET.get('page'))

    from ..enums.mouvements import TypeMouvement
    context = {
        'produit': produit,
        'stock_reel': stock_reel,
        'stock_total': stock_total,
        'valeur_totale': valeur_totale,
        'stocks_par_entrepot': stocks_par_entrepot,
        'mouvements': mouvements_page,
        'total_mouvements': total_mouvements,
        'sous_unites': produit.sous_unites.filter(actif=True),
        'lots': produit.lots.filter(actif=True).order_by('date_peremption') if hasattr(produit, 'lots') else [],
        'entrepots': Entrepot.objects.filter(actif=True).order_by('nom'),
        'types_mouvement': TypeMouvement.choices,
        'f': {'type': f_type, 'entrepot': f_entrepot, 'debut': f_debut, 'fin': f_fin},
    }
    return render(request, 'stock/produits/detail.html', context)


@csrf_exempt
def modifier_prix_produit(request, produit_id):
    """API pour modifier le prix de vente d'un produit"""
    
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
            nouveau_prix = Decimal(str(data.get('prix_vente', 0)))
            
            produit = get_object_or_404(Produit, id=produit_id)
            produit.prix_vente = nouveau_prix
            produit.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    return JsonResponse({'success': False, 'error': 'POST requis'})




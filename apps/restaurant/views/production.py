# apps/restaurant/views/production.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from decimal import Decimal
from django.db import transaction
import json
from datetime import date, timedelta

from ..models import Production, ProductionLigne, RecetteModel
from ..services.production_service import ProductionService
from apps.stock.models import Entrepot, StockEntrepot
from apps.rh.models import Employe


@login_required
def production_dashboard(request):
    entrepot_id = request.GET.get('entrepot_id')
    entrepot = get_object_or_404(Entrepot, id=entrepot_id) if entrepot_id else None

    recettes = RecetteModel.objects.filter(actif=True)

    recettes_dispo = []
    for recette in recettes:
        dispo = recette.verifier_disponibilite(entrepot=entrepot) if entrepot else {'disponible': False, 'manques': []}
        recettes_dispo.append({
            'id': recette.id,
            'code': recette.code,
            'nom': recette.nom,
            'type': recette.get_type_recette_display(),
            'portions_disponibles': dispo['disponible'],
            'manques': dispo['manques']
        })

    dernieres_productions = Production.objects.all().order_by('-date')[:10]

    context = {
        'recettes': recettes_dispo,
        'dernieres_productions': dernieres_productions,
        'entrepot': entrepot,
    }
    return render(request, 'restaurant/production/dashboard.html', context)


@login_required
def production_liste(request):
    productions = Production.objects.all().order_by('-date')
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
    production = get_object_or_404(Production, id=production_id)
    lignes = production.lignes.all()
    ingredients = production.ingredients.all()
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
    try:
        data = json.loads(request.body)
        recette_id = data.get('recette_id')
        entrepot_source_id = data.get('entrepot_source_id') or data.get('entrepot_id')
        entrepot_dest_id = data.get('entrepot_dest_id') or entrepot_source_id
        quantite = Decimal(str(data.get('quantite', 0)))

        if quantite <= 0:
            return JsonResponse({'success': False, 'error': 'Quantité invalide'})
        if not recette_id:
            return JsonResponse({'success': False, 'error': 'recette_id requis'})
        if not entrepot_source_id:
            return JsonResponse({'success': False, 'error': 'entrepot_source_id requis'})

        recette = get_object_or_404(RecetteModel, id=recette_id)
        entrepot_source = get_object_or_404(Entrepot, id=entrepot_source_id)
        entrepot_dest = get_object_or_404(Entrepot, id=entrepot_dest_id)

        employe = Employe.objects.filter(user=request.user).first()

        with transaction.atomic():
            production = Production.objects.create(
                entrepot_source=entrepot_source,
                entrepot_dest=entrepot_dest,
                produit_par=employe,
                notes=f"Production de {quantite} {recette.nom}"
            )

            ProductionLigne.objects.create(
                production=production,
                recette=recette,
                quantite=quantite
            )

            if data.get('valider', True):
                production.valider(employe if employe else request.user)

        return JsonResponse({
            'success': True,
            'message': f'{quantite} {recette.nom} produit(s)',
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
def api_verifier_stock(request, recette_id):
    try:
        recette = get_object_or_404(RecetteModel, id=recette_id)
        entrepot_id = request.GET.get('entrepot_id')
        if not entrepot_id:
            return JsonResponse({'success': False, 'error': 'entrepot_id requis'})
        entrepot = get_object_or_404(Entrepot, id=entrepot_id)

        manques = ProductionService.verifier_stock_ingredients(recette, entrepot=entrepot)

        return JsonResponse({
            'success': len(manques) == 0,
            'disponible': len(manques) == 0,
            'manques': manques
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_historique_production(request):
    try:
        jours = int(request.GET.get('jours', 30))
        statut = request.GET.get('statut')
        date_debut = date.today() - timedelta(days=jours)

        productions = Production.objects.filter(date__date__gte=date_debut).order_by('-date')
        if statut:
            productions = productions.filter(statut=statut)

        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 20))
        paginator = Paginator(productions, per_page)
        productions_page = paginator.get_page(page)

        data = []
        for p in productions_page:
            data.append({
                'id': p.id,
                'numero': p.numero,
                'date': p.date.strftime('%d/%m/%Y %H:%M'),
                'statut': p.statut,
                'total_unites': float(p.total_unites),
                'produit_par': p.produit_par.username if p.produit_par else None,
                'lignes': [
                    {
                        'recette': l.recette.nom,
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
    try:
        production = get_object_or_404(Production, id=production_id)

        lignes = []
        for l in production.lignes.all():
            lignes.append({
                'recette_id': l.recette.id,
                'recette_nom': l.recette.nom,
                'quantite': float(l.quantite)
            })

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
                'total_unites': float(production.total_unites)
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_stock_menu(request, menu_id):
    return JsonResponse({'success': False, 'error': 'Déprécié — utiliser api_verifier_stock'})

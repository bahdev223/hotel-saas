# apps/restaurant/views/menus.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
import uuid
import json

from ..models import MenuModel, LigneMenuModel, RecetteModel


@login_required
def menus_liste(request):
    """Liste des menus"""
    menus = MenuModel.objects.filter(actif=True).order_by('ordre_affichage', 'nom')
    
    search = request.GET.get('search')
    if search:
        menus = menus.filter(Q(nom__icontains=search) | Q(code__icontains=search))
    
    paginator = Paginator(menus, 20)
    page = request.GET.get('page')
    menus_page = paginator.get_page(page)
    
    context = {
        'menus': menus_page,
        'total': menus.count(),
        'types_menu': MenuModel.TYPE_MENU_CHOICES,
        'recettes': RecetteModel.objects.filter(actif=True),
        'groupes_choices': LigneMenuModel.GROUPE_CHOICES,
    }
    return render(request, 'restaurant/menus/liste.html', context)


@login_required
def menu_ajouter(request):
    """Ajouter un menu (redirige vers la liste avec modal)"""
    return redirect('restaurant:menus_liste')


@login_required
def menu_modifier(request, menu_id):
    """Modifier un menu (redirige vers la liste avec modal)"""
    return redirect('restaurant:menus_liste')


@login_required
@require_http_methods(["GET"])
def api_menu_get(request, menu_id):
    """API pour récupérer les infos d'un menu avec l'URL de l'image"""
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        return JsonResponse({
            'id': str(menu.id),
            'code': menu.code,
            'nom': menu.nom,
            'type_menu': menu.type_menu,
            'type_menu_display': menu.get_type_menu_display(),
            'prix_vente': float(menu.prix_vente) if menu.prix_vente else None,
            'ordre_affichage': menu.ordre_affichage,
            'visible_dans_pos': menu.visible_dans_pos,
            'description': menu.description or '',
            'image_url': menu.image.url if menu.image else None,
            'cout_revient': float(menu.get_cout_revient_total()),
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def api_menu_recettes(request, menu_id):
    """API pour récupérer les recettes d'un menu avec tous les détails"""
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        lignes = menu.lignes.all().select_related('recette')
        return JsonResponse({
            'recettes': [
                {
                    'id': str(ligne.id),
                    'recette_id': str(ligne.recette.id),
                    'recette_nom': ligne.recette.nom,
                    'groupe': ligne.groupe,
                    'type_ligne': ligne.type_ligne,
                    'quantite': ligne.quantite,
                    'prix_supplement': float(ligne.prix_supplement) if ligne.prix_supplement else 0
                } for ligne in lignes
            ],
            'cout_revient': float(menu.get_cout_revient_total()),
            'prix_vente': float(menu.prix_vente) if menu.prix_vente else 0
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_menu_ajouter(request):
    """API pour ajouter un menu avec image"""
    try:
        code = request.POST.get('code') or f"MENU-{uuid.uuid4().hex[:6].upper()}"
        
        menu = MenuModel.objects.create(
            code=code,
            nom=request.POST.get('nom'),
            type_menu=request.POST.get('type_menu'),
            prix_vente=request.POST.get('prix_vente') or None,
            description=request.POST.get('description', ''),
            visible_dans_pos=request.POST.get('visible_dans_pos') == 'on',
            ordre_affichage=int(request.POST.get('ordre_affichage', 0)),
            actif=True
        )
        
        print("=== DEBUG UPLOAD ===")
        print("POST data:", request.POST)
        print("FILES data:", request.FILES)
        # Gérer l'upload de l'image
        
        if request.FILES.get('image'):
            menu.image = request.FILES['image']
            menu.save()
        
        return JsonResponse({'success': True, 'menu_id': str(menu.id)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_menu_modifier(request, menu_id):
    """API pour modifier un menu avec image"""
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        menu.nom = request.POST.get('nom')
        menu.type_menu = request.POST.get('type_menu')
        menu.prix_vente = request.POST.get('prix_vente') or None
        menu.description = request.POST.get('description', '')
        menu.visible_dans_pos = request.POST.get('visible_dans_pos') == 'on'
        menu.ordre_affichage = int(request.POST.get('ordre_affichage', 0))
        
        # Gérer l'upload de l'image
        if request.FILES.get('image'):
            # Supprimer l'ancienne image si elle existe
            if menu.image:
                menu.image.delete(save=False)
            menu.image = request.FILES['image']
        
        menu.save()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_menu_ajouter_recette(request, menu_id):
    """API pour ajouter une recette au menu avec tous les paramètres"""
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        
        # Récupérer les données (support JSON et FormData)
        if request.content_type == 'application/json':
            data = json.loads(request.body)
            recette_id = data.get('recette_id')
            quantite = int(data.get('quantite', 1))
            groupe = data.get('groupe', 'PLAT')
            type_ligne = data.get('type_ligne', 'FIXE')
            prix_supplement = data.get('prix_supplement', 0)
        else:
            recette_id = request.POST.get('recette_id')
            quantite = int(request.POST.get('quantite', 1))
            groupe = request.POST.get('groupe', 'PLAT')
            type_ligne = request.POST.get('type_ligne', 'FIXE')
            prix_supplement = request.POST.get('prix_supplement', 0)
        
        ligne = LigneMenuModel.objects.create(
            id=str(uuid.uuid4())[:8],
            menu=menu,
            recette_id=recette_id,
            quantite=quantite,
            groupe=groupe,
            type_ligne=type_ligne,
            prix_supplement=prix_supplement or 0
        )
        
        # Recalculer le temps de préparation
        if hasattr(menu, 'calculer_temps_preparation'):
            menu.calculer_temps_preparation()
        
        return JsonResponse({'success': True, 'ligne_id': str(ligne.id)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_menu_supprimer_ligne(request, ligne_id):
    """API pour supprimer une ligne de menu"""
    try:
        ligne = get_object_or_404(LigneMenuModel, id=ligne_id)
        menu = ligne.menu
        ligne.delete()
        menu.calculer_temps_preparation()
        
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_menu_supprimer(request, menu_id):
    """API pour supprimer un menu"""
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        # Supprimer l'image associée
        if menu.image:
            menu.image.delete(save=False)
        menu.delete()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def api_menu_calculer_prix(request, menu_id=None):
    """
    API pour calculer le prix total d'un menu basé sur ses items
    """
    try:
        data = json.loads(request.body)
        menu_items = data.get('items', [])
        
        total_prix = 0
        for item in menu_items:
            prix = item.get('prix', 0)
            quantite = item.get('quantite', 1)
            total_prix += prix * quantite
        
        remise = data.get('remise', 0)
        if remise:
            total_prix = total_prix * (1 - remise / 100)
        
        return JsonResponse({
            'success': True,
            'prix_total': total_prix,
            'prix_ht': total_prix,
            'tva': total_prix * 0.2,
            'prix_ttc': total_prix * 1.2
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
        
# apps/restaurant/views/menus.py - Ajouter cette fonction

@login_required
def menu_composer(request, menu_id):
    """Page pour composer un menu"""
    menu = get_object_or_404(MenuModel, id=menu_id)
    recettes = RecetteModel.objects.filter(actif=True)
    
    context = {
        'menu': menu,
        'recettes': recettes,
        'types_menu': MenuModel.TYPE_MENU_CHOICES,
    }
    return render(request, 'restaurant/menus/composer.html', context)


@login_required
def api_menu_lignes(request, menu_id):
    """API pour récupérer les lignes d'un menu (pour le composer)"""
    try:
        menu = get_object_or_404(MenuModel, id=menu_id)
        lignes = menu.lignes.all().select_related('recette')
        return JsonResponse({
            'success': True,
            'lignes': [{
                'id': str(l.id),
                'recette_id': str(l.recette.id),
                'recette_nom': l.recette.nom,
                'groupe': l.groupe,
                'type_ligne': l.type_ligne,
                'quantite': l.quantite,
                'cout': float(l.get_cout()),
                'prix_supplement': float(l.prix_supplement) if l.prix_supplement else 0
            } for l in lignes]
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


# apps/restaurant/views/menus.py - Ajouter à la fin du fichier

@login_required
def api_menus_pos(request):
    """API pour récupérer les menus pour le POS"""
    try:
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
            })
        
        return JsonResponse({'success': True, 'menus': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def api_menu_detail(request, menu_id):
    """API pour récupérer le détail d'un menu avec ses recettes"""
    try:
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
                'prix_supplement': float(ligne.prix_supplement) if ligne.prix_supplement else 0
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
            },
            'recettes': recettes_data
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
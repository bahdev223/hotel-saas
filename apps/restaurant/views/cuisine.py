# apps/restaurant/views/cuisine.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import json
from decimal import Decimal

from apps.pos.models import Commande, LigneCommande
from apps.pos.constants import ActionPOS, TypePointVente
from apps.pos.services.access_service import POSAccessService
from apps.stock.models import StockEntrepot, Produit
from ..services.restaurant_service import RestaurantService, RestaurantWorkflowError


@login_required
def cuisine_dashboard(request):
    """KDS Restaurant : uniquement les préparateurs autorisés."""
    points = POSAccessService.points_accessibles(
        user=request.user,
        action=ActionPOS.GERER_CUISINE,
    ).filter(type=TypePointVente.RESTAURATION)
    if not points.exists():
        return render(
            request,
            'restaurant/cuisine/dashboard.html',
            {'points': [], 'access_denied': True},
            status=403,
        )
    return render(
        request,
        'restaurant/cuisine/dashboard.html',
        {'points': points, 'access_denied': False},
    )


@login_required
def api_cuisine_commandes(request):
    """Commandes Restaurant visibles par le KDS autorisé."""
    points = POSAccessService.points_accessibles(
        user=request.user,
        action=ActionPOS.GERER_CUISINE,
    ).filter(type=TypePointVente.RESTAURATION)
    point_ids = list(points.values_list("id", flat=True))
    if not point_ids:
        return JsonResponse(
            {'success': False, 'error': 'Accès cuisine refusé.'},
            status=403,
        )

    commandes = Commande.objects.filter(
        point_vente_id__in=point_ids,
        statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRETE'],
        type_commande__in=['SUR_PLACE', 'EMPORTER'],
    ).select_related(
        'table', 'point_vente', 'created_by'
    ).prefetch_related(
        'lignes__produit', 'lignes__menu'
    ).order_by('created_at')

    point_filter = request.GET.get('point_vente')
    if point_filter:
        commandes = commandes.filter(point_vente_id=point_filter)

    data = []
    for commande in commandes:
        temps_attente = int((timezone.now() - commande.created_at).total_seconds() / 60)
        lignes = []
        for ligne in commande.lignes.all():
            nom = (
                ligne.produit.nom if ligne.produit
                else ligne.menu.nom if ligne.menu
                else "Article"
            )
            lignes.append({
                'id': ligne.id,
                'nom': nom,
                'quantite': float(ligne.quantite),
                'notes': ligne.notes or "",
            })

        data.append({
            'id': commande.id,
            'numero': commande.numero,
            'table': commande.table.numero if commande.table else 'Emporter',
            'serveur': commande.created_by.nom_complet if commande.created_by else '',
            'point_vente_id': commande.point_vente_id,
            'point_vente': commande.point_vente.nom if commande.point_vente else '',
            'type': commande.get_type_commande_display(),
            'statut': commande.statut,
            'statut_display': commande.get_statut_display(),
            'temps_attente': temps_attente,
            'lignes': lignes,
            'notes': commande.notes or "",
        })

    return JsonResponse({'success': True, 'commandes': data})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_cuisine_changer_statut(request, commande_id):
    try:
        commande = get_object_or_404(
            Commande.objects.select_related("point_vente"),
            id=commande_id,
            point_vente__type=TypePointVente.RESTAURATION,
        )
        data = (
            json.loads(request.body or "{}")
            if request.content_type == "application/json"
            else request.POST
        )
        nouveau_statut = data.get("statut")

        if nouveau_statut == "EN_PREPARATION":
            commande = RestaurantService.demarrer_preparation(
                commande=commande,
                user=request.user,
            )
        elif nouveau_statut == "PRETE":
            commande = RestaurantService.marquer_prete(
                commande=commande,
                user=request.user,
            )
        else:
            return JsonResponse({
                'success': False,
                'error': (
                    "La cuisine ne peut gérer que EN_PREPARATION et PRETE. "
                    "Le service en salle marque ensuite la commande SERVIE."
                ),
            }, status=400)

        return JsonResponse({
            'success': True,
            'statut': commande.statut,
            'statut_display': commande.get_statut_display(),
        })
    except RestaurantWorkflowError as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=403)
    except Exception as exc:
        return JsonResponse({'success': False, 'error': str(exc)}, status=400)


@login_required
def api_cuisine_historique(request):
    """API pour l'historique des commandes servies"""
    point_ids = POSAccessService.points_accessibles(
        user=request.user,
        action=ActionPOS.GERER_CUISINE,
    ).filter(
        type=TypePointVente.RESTAURATION,
    ).values_list("id", flat=True)
    commandes = Commande.objects.filter(
        point_vente_id__in=point_ids,
        statut__in=['SERVIE', 'PAYEE'],
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
    commande = get_object_or_404(
        Commande.objects.select_related("point_vente"),
        id=commande_id,
        point_vente__type=TypePointVente.RESTAURATION,
    )
    decision = POSAccessService.check(
        user=request.user,
        point_vente=commande.point_vente,
        action=ActionPOS.GERER_CUISINE,
    )
    if not decision.allowed:
        return JsonResponse({'success': False, 'error': 'Accès cuisine refusé.'}, status=403)

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

@login_required
def api_commande_ingredients(request, commande_id):
    """Besoins stock agrégés de la commande pour le KDS."""
    commande = get_object_or_404(
        Commande.objects.select_related("point_vente", "entrepot"),
        id=commande_id,
        point_vente__type=TypePointVente.RESTAURATION,
    )
    decision = POSAccessService.check(
        user=request.user,
        point_vente=commande.point_vente,
        action=ActionPOS.GERER_CUISINE,
    )
    if not decision.allowed:
        return JsonResponse(
            {
                "success": False,
                "error": f"Accès cuisine refusé ({decision.reason}).",
            },
            status=403,
        )
    if commande.entrepot_id is None:
        return JsonResponse(
            {
                "success": False,
                "error": "Aucun entrepôt de préparation n'est lié à la commande.",
            },
            status=400,
        )

    from ..services.consumption_service import RestaurantConsumptionService

    besoins = RestaurantConsumptionService.calculer_besoins_commande(commande)
    stocks = {
        row.produit_id: row.quantite
        for row in StockEntrepot.objects.filter(
            entrepot=commande.entrepot,
            produit_id__in=list(besoins.keys()),
        )
    }
    produits = {
        produit.id: produit
        for produit in Produit.objects.filter(id__in=list(besoins.keys()))
    }

    ingredients = []
    for produit_id, quantite_requise in besoins.items():
        produit = produits.get(produit_id)
        quantite_dispo = stocks.get(produit_id, Decimal("0"))
        ingredients.append({
            "id": produit_id,
            "nom": produit.nom if produit else "Inconnu",
            "quantite": float(quantite_requise),
            "unite": produit.unite_base if produit else "",
            "stock": float(quantite_dispo),
            "disponible": quantite_dispo >= quantite_requise,
        })

    verification = RestaurantConsumptionService.verifier_disponibilite_commande(
        commande,
        commande.entrepot,
    )
    return JsonResponse({
        "success": True,
        "commande_id": commande.id,
        "disponible": verification["disponible"],
        "ingredients": ingredients,
        "stock_manquant": verification["manques"],
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_lancer_cuisson(request, commande_id):
    """Compatibilité ancienne UI : délègue au workflow KDS unique."""
    try:
        commande = get_object_or_404(
            Commande.objects.select_related("point_vente", "entrepot"),
            id=commande_id,
            point_vente__type=TypePointVente.RESTAURATION,
        )
        data = json.loads(request.body or "{}")
        if data.get("mode", "auto") != "auto":
            return JsonResponse(
                {
                    "success": False,
                    "error": (
                        "Le déstockage manuel est désactivé. "
                        "Corrigez la recette/commande puis relancez la préparation."
                    ),
                },
                status=400,
            )

        commande = RestaurantService.demarrer_preparation(
            commande=commande,
            user=request.user,
        )
        return JsonResponse({
            "success": True,
            "message": f"Préparation lancée pour commande #{commande.numero}",
            "statut": commande.statut,
            "statut_display": commande.get_statut_display(),
        })
    except RestaurantWorkflowError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

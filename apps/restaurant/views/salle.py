import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from apps.pos.constants import ActionPOS, TypePointVente
from apps.pos.services.access_service import POSAccessService
from apps.restaurant.models import SalleModel, TableModel
from apps.restaurant.services.restaurant_service import (
    RestaurantService,
    RestaurantWorkflowError,
)


def _points_salle(user):
    return POSAccessService.points_accessibles(
        user=user,
        action=ActionPOS.GERER_SALLE,
    ).filter(type=TypePointVente.RESTAURATION)


@login_required
def salle_dashboard(request):
    points = _points_salle(request.user)
    selected = None
    point_id = request.GET.get("point_vente")
    if point_id:
        selected = points.filter(pk=point_id).first()
    if selected is None:
        selected = points.first()

    salles = (
        SalleModel.objects.filter(point_vente=selected, actif=True)
        .prefetch_related("tables")
        .order_by("ordre", "nom")
        if selected else SalleModel.objects.none()
    )
    return render(request, "restaurant/salle/dashboard.html", {
        "points": points,
        "point_vente": selected,
        "salles": salles,
    })


@login_required
def api_salle_etat(request):
    points = _points_salle(request.user)
    point_id = request.GET.get("point_vente")
    point = (
        points.filter(pk=point_id).first()
        if point_id else points.first()
    )
    if point is None:
        return JsonResponse(
            {"success": False, "error": "Aucun Restaurant accessible."},
            status=403,
        )

    salles = SalleModel.objects.filter(
        point_vente=point,
        actif=True,
    ).prefetch_related("tables__serveur_actuel").order_by("ordre", "nom")

    data = []
    for salle in salles:
        tables = []
        for table in salle.tables.filter(actif=True).order_by("numero"):
            commande = RestaurantService.commande_active_table(table)
            if commande:
                if commande.statut == "SERVIE" and table.statut != "A_ENCAISSER":
                    table.statut = "A_ENCAISSER"
                    table.save(update_fields=["statut", "updated_at"])
                elif (
                    commande.statut in ("EN_ATTENTE", "EN_PREPARATION", "PRETE")
                    and table.statut != "COMMANDE_EN_COURS"
                ):
                    table.statut = "COMMANDE_EN_COURS"
                    table.save(update_fields=["statut", "updated_at"])
            elif table.statut in ("COMMANDE_EN_COURS", "A_ENCAISSER"):
                table.statut = "LIBRE"
                table.serveur_actuel = None
                table.heure_arrivee = None
                table.nombre_couverts = 0
                table.save(update_fields=[
                    "statut", "serveur_actuel", "heure_arrivee",
                    "nombre_couverts", "updated_at",
                ])

            tables.append({
                "id": table.id,
                "numero": table.numero,
                "capacite": table.capacite,
                "statut": table.statut,
                "statut_label": table.get_statut_display(),
                "nombre_couverts": table.nombre_couverts,
                "serveur": (
                    table.serveur_actuel.nom_complet
                    if table.serveur_actuel else ""
                ),
                "heure_arrivee": (
                    table.heure_arrivee.isoformat()
                    if table.heure_arrivee else None
                ),
                "commande": {
                    "id": commande.id,
                    "numero": commande.numero,
                    "statut": commande.statut,
                    "statut_label": commande.get_statut_display(),
                    "montant": float(commande.montant_total),
                    "temps_attente": commande.temps_attente_minutes,
                    "client": commande.client_nom or "",
                } if commande else None,
                "commande_url": (
                    f"{reverse('pos:pos_by_slug', args=[point.code])}"
                    f"?table_id={table.id}"
                ),
            })
        data.append({
            "id": salle.id,
            "code": salle.code,
            "nom": salle.nom,
            "tables": tables,
        })

    return JsonResponse({
        "success": True,
        "point_vente": {
            "id": point.id,
            "code": point.code,
            "nom": point.nom,
        },
        "salles": data,
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_table_occuper(request, table_id):
    try:
        table = get_object_or_404(
            TableModel.objects.select_related("salle__point_vente"),
            id=table_id,
            actif=True,
        )
        employe = getattr(request.user, "employe", None)
        if employe is None:
            return JsonResponse(
                {"success": False, "error": "Profil employé requis."},
                status=403,
            )
        data = json.loads(request.body or "{}")
        table = RestaurantService.occuper_table(
            table=table,
            employe=employe,
            user=request.user,
            nombre_couverts=data.get("nombre_couverts"),
        )
        return JsonResponse({
            "success": True,
            "table_id": table.id,
            "statut": table.statut,
        })
    except RestaurantWorkflowError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_table_liberer(request, table_id):
    try:
        table = get_object_or_404(
            TableModel.objects.select_related("salle__point_vente"),
            id=table_id,
            actif=True,
        )
        point = table.point_vente
        if not point:
            raise RestaurantWorkflowError("Table sans salle Restaurant.")
        decision = POSAccessService.check(
            user=request.user,
            point_vente=point,
            action=ActionPOS.GERER_SALLE,
        )
        if not decision.allowed:
            return JsonResponse(
                {"success": False, "error": f"Accès refusé ({decision.reason})."},
                status=403,
            )
        if RestaurantService.commande_active_table(table):
            return JsonResponse({
                "success": False,
                "error": "Impossible de libérer une table avec une commande active.",
            }, status=409)

        table.statut = "LIBRE"
        table.serveur_actuel = None
        table.heure_arrivee = None
        table.nombre_couverts = 0
        table.save(update_fields=[
            "statut", "serveur_actuel", "heure_arrivee",
            "nombre_couverts", "updated_at",
        ])
        return JsonResponse({"success": True, "table_id": table.id})
    except RestaurantWorkflowError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_servir_commande(request, commande_id):
    from apps.pos.models import Commande
    try:
        commande = get_object_or_404(
            Commande.objects.select_related("point_vente", "table"),
            id=commande_id,
            point_vente__type=TypePointVente.RESTAURATION,
        )
        commande = RestaurantService.servir(
            commande=commande,
            user=request.user,
        )
        return JsonResponse({
            "success": True,
            "commande_id": commande.id,
            "statut": commande.statut,
            "statut_label": commande.get_statut_display(),
            "table_id": commande.table_id,
        })
    except RestaurantWorkflowError as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=409)
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

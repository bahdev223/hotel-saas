import json

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from apps.pos.constants import ActionPOS, TypePointVente
from apps.authentication.groups import MANAGER, PATRON
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


def _can_configure_salle(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name__in=[PATRON, MANAGER]).exists()
        )
    )


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
        "can_configure": _can_configure_salle(request.user),
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
                "salle_id": table.salle_id,
                "numero": table.numero,
                "capacite": table.capacite,
                "actif": table.actif,
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
            "ordre": salle.ordre,
            "actif": salle.actif,
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


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_salle_enregistrer(request):
    if not _can_configure_salle(request.user):
        return JsonResponse(
            {"success": False, "error": "Configuration réservée à la direction/manager."},
            status=403,
        )
    try:
        data = json.loads(request.body or "{}")
        point = get_object_or_404(
            _points_salle(request.user),
            id=data.get("point_vente_id"),
        )
        salle_id = data.get("id")
        salle = (
            get_object_or_404(
                SalleModel,
                id=salle_id,
                point_vente=point,
            )
            if salle_id
            else SalleModel(point_vente=point)
        )
        nom = (data.get("nom") or "").strip()
        code = (data.get("code") or "").strip().upper()
        if not nom or not code:
            return JsonResponse(
                {"success": False, "error": "Nom et code de salle obligatoires."},
                status=400,
            )
        duplicate = SalleModel.objects.filter(
            point_vente=point,
            code=code,
        )
        if salle.pk:
            duplicate = duplicate.exclude(pk=salle.pk)
        if duplicate.exists():
            return JsonResponse(
                {"success": False, "error": "Ce code de salle existe déjà."},
                status=409,
            )

        salle.nom = nom
        salle.code = code
        salle.ordre = max(0, int(data.get("ordre") or 0))
        salle.actif = bool(data.get("actif", True))
        salle.full_clean()
        salle.save()
        return JsonResponse({
            "success": True,
            "salle": {
                "id": salle.id,
                "code": salle.code,
                "nom": salle.nom,
                "ordre": salle.ordre,
                "actif": salle.actif,
            },
        })
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_table_enregistrer(request):
    if not _can_configure_salle(request.user):
        return JsonResponse(
            {"success": False, "error": "Configuration réservée à la direction/manager."},
            status=403,
        )
    try:
        data = json.loads(request.body or "{}")
        salle = get_object_or_404(
            SalleModel.objects.select_related("point_vente"),
            id=data.get("salle_id"),
            actif=True,
            point_vente__type=TypePointVente.RESTAURATION,
        )
        if not _points_salle(request.user).filter(id=salle.point_vente_id).exists():
            return JsonResponse(
                {"success": False, "error": "Restaurant non accessible."},
                status=403,
            )

        table_id = data.get("id")
        table = (
            get_object_or_404(
                TableModel.objects.select_for_update(),
                id=table_id,
            )
            if table_id
            else TableModel()
        )

        if table.pk:
            active_order = RestaurantService.commande_active_table(table)
            change_scope = table.salle_id != salle.id
            disabling = not bool(data.get("actif", table.actif))
            if active_order and (change_scope or disabling):
                return JsonResponse({
                    "success": False,
                    "error": (
                        "Impossible de déplacer/désactiver une table avec "
                        f"la commande active #{active_order.numero}."
                    ),
                }, status=409)

        numero = (data.get("numero") or "").strip()
        if not numero:
            return JsonResponse(
                {"success": False, "error": "Numéro de table obligatoire."},
                status=400,
            )
        capacite = int(data.get("capacite") or 1)
        if capacite < 1:
            return JsonResponse(
                {"success": False, "error": "La capacité doit être au moins 1."},
                status=400,
            )

        duplicate = TableModel.objects.filter(
            salle=salle,
            numero=numero,
        )
        if table.pk:
            duplicate = duplicate.exclude(pk=table.pk)
        if duplicate.exists():
            return JsonResponse(
                {"success": False, "error": "Ce numéro existe déjà dans cette salle."},
                status=409,
            )

        table.salle = salle
        table.numero = numero
        table.capacite = capacite
        table.actif = bool(data.get("actif", True))
        if not table.pk:
            table.statut = "LIBRE"
        table.save()

        return JsonResponse({
            "success": True,
            "table": {
                "id": table.id,
                "numero": table.numero,
                "capacite": table.capacite,
                "salle_id": table.salle_id,
                "actif": table.actif,
                "statut": table.statut,
            },
        })
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_table_desactiver(request, table_id):
    if not _can_configure_salle(request.user):
        return JsonResponse(
            {"success": False, "error": "Configuration réservée à la direction/manager."},
            status=403,
        )
    try:
        table = get_object_or_404(
            TableModel.objects.select_for_update().select_related("salle__point_vente"),
            id=table_id,
        )
        if not _points_salle(request.user).filter(id=table.salle.point_vente_id).exists():
            return JsonResponse(
                {"success": False, "error": "Restaurant non accessible."},
                status=403,
            )
        active_order = RestaurantService.commande_active_table(table)
        if active_order:
            return JsonResponse({
                "success": False,
                "error": f"Commande #{active_order.numero} encore active sur cette table.",
            }, status=409)

        table.actif = False
        table.statut = "HORS_SERVICE"
        table.serveur_actuel = None
        table.heure_arrivee = None
        table.nombre_couverts = 0
        table.save(update_fields=[
            "actif", "statut", "serveur_actuel",
            "heure_arrivee", "nombre_couverts", "updated_at",
        ])
        return JsonResponse({"success": True, "table_id": table.id})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

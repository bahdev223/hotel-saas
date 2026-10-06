import json
from datetime import date, time

from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods

from apps.authentication.groups import MANAGER, PATRON
from apps.rh.models import Employe

from ..constants import (
    ActionPOS,
    ModeAccesPOS,
    POINTS_VENTE_OPERATIONNELS,
    ROLE_PERMISSION_PRESETS,
    RolePOS,
)
from ..models import (
    AffectationPointVente,
    HoraireAffectation,
    PointVente,
    SessionCaisse,
)
from ..services.access_service import ACTION_PERMISSION_FIELDS, POSAccessService


_PERMISSION_FIELDS = tuple(
    field
    for action, field in ACTION_PERMISSION_FIELDS.items()
    if action != ActionPOS.ACCEDER and field
)
_ACTION_BY_FIELD = {
    field: action
    for action, field in ACTION_PERMISSION_FIELDS.items()
    if field
}


def _can_manage_access(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name__in=[PATRON, MANAGER]).exists()
        )
    )


def _can_grant_total(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name=PATRON).exists()
        )
    )


def _forbidden():
    return JsonResponse(
        {
            "success": False,
            "error": "Gestion des accès POS réservée à la direction/manager.",
        },
        status=403,
    )


def _parse_date(value, field):
    if value in (None, ""):
        return None
    try:
        return date.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field}: date invalide (AAAA-MM-JJ).") from exc


def _parse_time(value, field):
    if not value:
        raise ValueError(f"{field} est obligatoire.")
    try:
        return time.fromisoformat(str(value))
    except ValueError as exc:
        raise ValueError(f"{field}: heure invalide (HH:MM).") from exc


def _date_ranges_overlap(a, b):
    a_start = a.get("date_debut") or date.min
    a_end = a.get("date_fin") or date.max
    b_start = b.get("date_debut") or date.min
    b_end = b.get("date_fin") or date.max
    return a_start <= b_end and b_start <= a_end


def _weekly_interval(item):
    start_minutes = item["heure_debut"].hour * 60 + item["heure_debut"].minute
    end_minutes = item["heure_fin"].hour * 60 + item["heure_fin"].minute
    start = item["jour_semaine"] * 1440 + start_minutes
    end = item["jour_semaine"] * 1440 + end_minutes
    if end <= start:
        end += 7 * 1440 if item["jour_semaine"] == 6 else 1440
    return start, end


def _weekly_overlap(a, b):
    week = 7 * 1440
    a_start, a_end = _weekly_interval(a)
    b_start, b_end = _weekly_interval(b)
    for a_shift in (-week, 0, week):
        for b_shift in (-week, 0, week):
            left_start, left_end = a_start + a_shift, a_end + a_shift
            right_start, right_end = b_start + b_shift, b_end + b_shift
            if left_start < right_end and right_start < left_end:
                return True
    return False


def _normaliser_horaires(raw_horaires):
    if not isinstance(raw_horaires, list):
        raise ValueError("horaires doit être une liste.")

    result = []
    for index, raw in enumerate(raw_horaires, start=1):
        try:
            jour = int(raw.get("jour_semaine"))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Horaire #{index}: jour_semaine invalide.") from exc
        if jour not in range(7):
            raise ValueError(f"Horaire #{index}: jour_semaine doit être compris entre 0 et 6.")

        item = {
            "jour_semaine": jour,
            "heure_debut": _parse_time(raw.get("heure_debut"), f"Horaire #{index} heure_debut"),
            "heure_fin": _parse_time(raw.get("heure_fin"), f"Horaire #{index} heure_fin"),
            "date_debut": _parse_date(raw.get("date_debut"), f"Horaire #{index} date_debut"),
            "date_fin": _parse_date(raw.get("date_fin"), f"Horaire #{index} date_fin"),
            "actif": bool(raw.get("actif", True)),
        }
        if item["date_debut"] and item["date_fin"] and item["date_debut"] > item["date_fin"]:
            raise ValueError(f"Horaire #{index}: date_debut est après date_fin.")
        result.append(item)

    actifs = [item for item in result if item["actif"]]
    for i, left in enumerate(actifs):
        for right in actifs[i + 1:]:
            if (
                _date_ranges_overlap(left, right)
                and _weekly_overlap(left, right)
            ):
                raise ValueError(
                    "Deux horaires actifs se chevauchent pour cette affectation."
                )
    return result


def _permissions_for_payload(data, *, role, existing=None):
    explicit = data.get("permissions")
    apply_preset = bool(data.get("appliquer_preset", False))

    if explicit is None and existing is not None and not apply_preset:
        return {
            field: bool(getattr(existing, field))
            for field in _PERMISSION_FIELDS
        }

    result = {field: False for field in _PERMISSION_FIELDS}
    preset = ROLE_PERMISSION_PRESETS.get(role, {})
    for field, action in _ACTION_BY_FIELD.items():
        result[field] = bool(preset.get(action, False))

    if isinstance(explicit, dict):
        for field in _PERMISSION_FIELDS:
            if field in explicit:
                result[field] = bool(explicit[field])
    return result


def _serialize_horaire(horaire):
    return {
        "id": horaire.id,
        "jour_semaine": horaire.jour_semaine,
        "jour_label": horaire.get_jour_semaine_display(),
        "heure_debut": horaire.heure_debut.strftime("%H:%M"),
        "heure_fin": horaire.heure_fin.strftime("%H:%M"),
        "date_debut": horaire.date_debut.isoformat() if horaire.date_debut else None,
        "date_fin": horaire.date_fin.isoformat() if horaire.date_fin else None,
        "traverse_minuit": horaire.traverse_minuit,
        "actif": horaire.actif,
    }


def _serialize_affectation(affectation, *, include_decision=True):
    data = {
        "id": affectation.id,
        "employe": {
            "id": affectation.employe_id,
            "matricule": affectation.employe.matricule,
            "nom": affectation.employe.nom_complet,
        },
        "point_vente": {
            "id": affectation.point_vente_id,
            "code": affectation.point_vente.code,
            "nom": affectation.point_vente.nom,
            "type": affectation.point_vente.type,
        },
        "role": affectation.role,
        "role_label": affectation.get_role_display(),
        "mode_acces": affectation.mode_acces,
        "mode_acces_label": affectation.get_mode_acces_display(),
        "date_debut": affectation.date_debut.isoformat() if affectation.date_debut else None,
        "date_fin": affectation.date_fin.isoformat() if affectation.date_fin else None,
        "principal": affectation.principal,
        "actif": affectation.actif,
        "permissions": {
            field: bool(getattr(affectation, field))
            for field in _PERMISSION_FIELDS
        },
        "horaires": [
            _serialize_horaire(h)
            for h in affectation.horaires.all()
        ],
    }
    if include_decision and affectation.employe.user_id:
        decision = POSAccessService.check(
            user=affectation.employe.user,
            employe=affectation.employe,
            point_vente=affectation.point_vente,
            action=ActionPOS.ACCEDER,
        )
        data["acces_actuel"] = decision.to_dict()
    return data


@login_required
@require_GET
def api_acces_liste(request):
    if not _can_manage_access(request.user):
        return _forbidden()

    qs = (
        AffectationPointVente.objects
        .filter(point_vente__type__in=POINTS_VENTE_OPERATIONNELS)
        .select_related("employe", "employe__user", "point_vente")
        .prefetch_related("horaires")
        .order_by("point_vente__type", "point_vente__nom", "employe__nom", "employe__prenom")
    )
    point_id = request.GET.get("point_vente")
    employe_id = request.GET.get("employe")
    actif = request.GET.get("actif")
    if point_id:
        qs = qs.filter(point_vente_id=point_id)
    if employe_id:
        qs = qs.filter(employe_id=employe_id)
    if actif in ("0", "1"):
        qs = qs.filter(actif=(actif == "1"))

    return JsonResponse({
        "success": True,
        "affectations": [_serialize_affectation(a) for a in qs],
        "meta": {
            "modes": list(ModeAccesPOS.choices),
            "roles": list(RolePOS.choices),
            "permission_fields": list(_PERMISSION_FIELDS),
            "can_grant_total": _can_grant_total(request.user),
        },
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_affectation_enregistrer(request):
    if not _can_manage_access(request.user):
        return _forbidden()

    try:
        data = json.loads(request.body or "{}")
        affectation_id = data.get("id")
        employe = get_object_or_404(Employe, id=data.get("employe_id"), actif=True)
        point_vente = get_object_or_404(
            PointVente,
            id=data.get("point_vente_id"),
            actif=True,
            type__in=POINTS_VENTE_OPERATIONNELS,
        )
        role = data.get("role") or RolePOS.CAISSIER
        mode = data.get("mode_acces") or ModeAccesPOS.PERMANENT

        if role not in RolePOS.values:
            return JsonResponse({"success": False, "error": "Rôle POS invalide."}, status=400)
        if mode not in ModeAccesPOS.values:
            return JsonResponse({"success": False, "error": "Mode d'accès invalide."}, status=400)
        if mode == ModeAccesPOS.TOTAL and not _can_grant_total(request.user):
            return JsonResponse({
                "success": False,
                "error": "Seul le patron/superuser peut attribuer un accès TOTAL.",
            }, status=403)

        existing = None
        if affectation_id:
            existing = get_object_or_404(
                AffectationPointVente.objects.select_for_update(),
                id=affectation_id,
            )
            if existing.mode_acces == ModeAccesPOS.TOTAL and not _can_grant_total(request.user):
                return JsonResponse({
                    "success": False,
                    "error": "Seul le patron/superuser peut modifier un accès TOTAL.",
                }, status=403)

        if mode == ModeAccesPOS.TOTAL:
            other_total = AffectationPointVente.objects.filter(
                employe=employe,
                mode_acces=ModeAccesPOS.TOTAL,
                actif=True,
            )
            if existing:
                other_total = other_total.exclude(pk=existing.pk)
            if other_total.exists():
                return JsonResponse({
                    "success": False,
                    "error": "Cet employé possède déjà un accès TOTAL actif.",
                }, status=409)

        permissions = _permissions_for_payload(data, role=role, existing=existing)
        date_debut = _parse_date(data.get("date_debut"), "date_debut")
        date_fin = _parse_date(data.get("date_fin"), "date_fin")
        if date_debut and date_fin and date_debut > date_fin:
            return JsonResponse({
                "success": False,
                "error": "date_debut ne peut pas être après date_fin.",
            }, status=400)

        try:
            if existing is None:
                affectation = AffectationPointVente.objects.create(
                    employe=employe,
                    point_vente=point_vente,
                    role=role,
                    mode_acces=mode,
                    date_debut=date_debut,
                    date_fin=date_fin,
                    principal=bool(data.get("principal", False)),
                    actif=bool(data.get("actif", True)),
                    **permissions,
                )
            else:
                affectation = existing
                affectation.employe = employe
                affectation.point_vente = point_vente
                affectation.role = role
                affectation.mode_acces = mode
                affectation.date_debut = date_debut
                affectation.date_fin = date_fin
                affectation.principal = bool(data.get("principal", affectation.principal))
                affectation.actif = bool(data.get("actif", affectation.actif))
                for field, value in permissions.items():
                    setattr(affectation, field, value)
                affectation.save()
        except IntegrityError:
            return JsonResponse({
                "success": False,
                "error": "Une affectation identique existe déjà pour cet employé.",
            }, status=409)

        if affectation.principal:
            AffectationPointVente.objects.filter(
                employe=employe,
                actif=True,
            ).exclude(pk=affectation.pk).update(principal=False)

        affectation = (
            AffectationPointVente.objects
            .select_related("employe", "employe__user", "point_vente")
            .prefetch_related("horaires")
            .get(pk=affectation.pk)
        )
        return JsonResponse({
            "success": True,
            "affectation": _serialize_affectation(affectation),
        })

    except (ValueError, TypeError) as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_affectation_desactiver(request, affectation_id):
    if not _can_manage_access(request.user):
        return _forbidden()

    affectation = get_object_or_404(
        AffectationPointVente.objects.select_for_update().select_related(
            "employe", "point_vente"
        ),
        id=affectation_id,
    )
    if affectation.mode_acces == ModeAccesPOS.TOTAL and not _can_grant_total(request.user):
        return JsonResponse({
            "success": False,
            "error": "Seul le patron/superuser peut désactiver un accès TOTAL.",
        }, status=403)

    sessions = SessionCaisse.objects.filter(
        ouverte_par=affectation.employe,
        statut__in=("OUVERTE", "EN_COMPTAGE"),
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )
    if affectation.mode_acces != ModeAccesPOS.TOTAL:
        sessions = sessions.filter(point_vente=affectation.point_vente)
    if sessions.exists():
        return JsonResponse({
            "success": False,
            "error": "Fermez d'abord la session de caisse active de cet employé.",
        }, status=409)

    affectation.actif = False
    affectation.principal = False
    affectation.save(update_fields=["actif", "principal"])
    return JsonResponse({"success": True, "id": affectation.id, "actif": False})


@login_required
@require_GET
def api_horaires_affectation(request, affectation_id):
    if not _can_manage_access(request.user):
        return _forbidden()

    affectation = get_object_or_404(
        AffectationPointVente.objects.select_related("employe", "point_vente"),
        id=affectation_id,
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )
    horaires = affectation.horaires.all().order_by("jour_semaine", "heure_debut")
    return JsonResponse({
        "success": True,
        "affectation_id": affectation.id,
        "mode_acces": affectation.mode_acces,
        "horaires": [_serialize_horaire(h) for h in horaires],
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_horaires_remplacer(request, affectation_id):
    if not _can_manage_access(request.user):
        return _forbidden()

    affectation = get_object_or_404(
        AffectationPointVente.objects.select_for_update().select_related(
            "employe", "point_vente"
        ),
        id=affectation_id,
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )
    try:
        data = json.loads(request.body or "{}")
        horaires = _normaliser_horaires(data.get("horaires", []))
    except (ValueError, TypeError) as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

    affectation.horaires.all().delete()
    HoraireAffectation.objects.bulk_create([
        HoraireAffectation(affectation=affectation, **item)
        for item in horaires
    ])

    if bool(data.get("activer_mode_horaires", True)):
        if affectation.mode_acces == ModeAccesPOS.TOTAL and not _can_grant_total(request.user):
            return JsonResponse({
                "success": False,
                "error": "Vous ne pouvez pas modifier un accès TOTAL.",
            }, status=403)
        affectation.mode_acces = ModeAccesPOS.HORAIRES
        affectation.save(update_fields=["mode_acces"])

    return JsonResponse({
        "success": True,
        "affectation_id": affectation.id,
        "mode_acces": affectation.mode_acces,
        "horaires": [
            _serialize_horaire(h)
            for h in affectation.horaires.all().order_by("jour_semaine", "heure_debut")
        ],
    })


@login_required
@require_GET
def api_acces_etat(request, point_vente_id):
    point_vente = get_object_or_404(
        PointVente,
        id=point_vente_id,
        actif=True,
        type__in=POINTS_VENTE_OPERATIONNELS,
    )
    decision = POSAccessService.check(
        user=request.user,
        point_vente=point_vente,
        action=request.GET.get("action") or ActionPOS.ACCEDER,
    )
    return JsonResponse({"success": True, "acces": decision.to_dict()})

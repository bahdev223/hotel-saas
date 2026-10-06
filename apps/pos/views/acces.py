from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from apps.authentication.groups import MANAGER, PATRON
from apps.rh.models import Employe
from ..constants import ModeAccesPOS, POINTS_VENTE_OPERATIONNELS, RolePOS
from ..models import AffectationPointVente, HoraireAffectation, PointVente


PERMISSION_FIELDS = (
    "peut_vendre",
    "peut_encaisser",
    "peut_ouvrir_caisse",
    "peut_fermer_caisse",
    "peut_annuler_vente",
    "peut_accorder_remise",
    "peut_consulter_rapports",
)


def _can_manage_access(user):
    return bool(
        user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.groups.filter(name__in=[PATRON, MANAGER]).exists()
        )
    )


def _forbidden():
    return JsonResponse(
        {"success": False, "error": "Accès POS réservé à la direction et au manager."},
        status=403,
    )


def _parse_date(value):
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def _parse_time(value):
    if not value:
        return None
    return datetime.strptime(value, "%H:%M").time()


def _serialize_horaire(h):
    return {
        "id": h.id,
        "jour_semaine": h.jour_semaine,
        "jour_label": h.get_jour_semaine_display(),
        "heure_debut": h.heure_debut.strftime("%H:%M"),
        "heure_fin": h.heure_fin.strftime("%H:%M"),
        "date_debut": h.date_debut.isoformat() if h.date_debut else None,
        "date_fin": h.date_fin.isoformat() if h.date_fin else None,
        "actif": h.actif,
        "traverse_minuit": h.traverse_minuit,
    }


def _serialize_affectation(a):
    return {
        "id": a.id,
        "employe_id": a.employe_id,
        "employe": a.employe.nom_complet,
        "matricule": a.employe.matricule or "",
        "point_vente_id": a.point_vente_id,
        "point_vente": a.point_vente.nom,
        "point_vente_type": a.point_vente.type,
        "role": a.role,
        "role_label": a.get_role_display(),
        "mode_acces": a.mode_acces,
        "mode_acces_label": a.get_mode_acces_display(),
        "date_debut": a.date_debut.isoformat() if a.date_debut else None,
        "date_fin": a.date_fin.isoformat() if a.date_fin else None,
        "principal": a.principal,
        "actif": a.actif,
        "permissions": {field: bool(getattr(a, field)) for field in PERMISSION_FIELDS},
        "horaires": [_serialize_horaire(h) for h in a.horaires.all()],
    }


@login_required
def acces_view(request):
    if not _can_manage_access(request.user):
        messages.error(request, "La gestion des accès POS est réservée à la direction et au manager.")
        return redirect("pos:employe_dashboard")

    context = {
        "points": PointVente.objects.filter(
            actif=True,
            type__in=POINTS_VENTE_OPERATIONNELS,
        ).order_by("type", "nom"),
        "employes": Employe.objects.filter(actif=True).order_by("nom", "prenom"),
        "roles": RolePOS.choices,
        "modes": ModeAccesPOS.choices,
        "jours": HoraireAffectation.JourSemaine.choices,
    }
    return render(request, "pos/acces.html", context)


@login_required
def api_acces_liste(request):
    if not _can_manage_access(request.user):
        return _forbidden()

    qs = AffectationPointVente.objects.filter(
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    ).select_related("employe", "point_vente").prefetch_related("horaires").order_by(
        "employe__nom", "employe__prenom", "point_vente__nom", "role"
    )

    employe_id = request.GET.get("employe")
    point_vente_id = request.GET.get("point_vente")
    mode = request.GET.get("mode")
    actif = request.GET.get("actif")

    if employe_id:
        qs = qs.filter(employe_id=employe_id)
    if point_vente_id:
        qs = qs.filter(point_vente_id=point_vente_id)
    if mode:
        qs = qs.filter(mode_acces=mode)
    if actif in {"0", "1"}:
        qs = qs.filter(actif=(actif == "1"))

    return JsonResponse({
        "success": True,
        "affectations": [_serialize_affectation(a) for a in qs],
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_acces_enregistrer(request):
    if not _can_manage_access(request.user):
        return _forbidden()

    import json
    data = json.loads(request.body or "{}")

    affectation_id = data.get("id")
    employe = get_object_or_404(Employe, id=data.get("employe_id"), actif=True)
    point_vente = get_object_or_404(
        PointVente,
        id=data.get("point_vente_id"),
        actif=True,
        type__in=POINTS_VENTE_OPERATIONNELS,
    )

    role = data.get("role")
    mode_acces = data.get("mode_acces")
    if role not in RolePOS.values:
        return JsonResponse({"success": False, "error": "Rôle POS invalide."}, status=400)
    if mode_acces not in ModeAccesPOS.values:
        return JsonResponse({"success": False, "error": "Mode d'accès invalide."}, status=400)

    date_debut = _parse_date(data.get("date_debut"))
    date_fin = _parse_date(data.get("date_fin"))
    if date_debut and date_fin and date_fin < date_debut:
        return JsonResponse({
            "success": False,
            "error": "La date de fin doit être postérieure à la date de début.",
        }, status=400)

    if affectation_id:
        affectation = get_object_or_404(
            AffectationPointVente,
            id=affectation_id,
            point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
        )
        duplicate = AffectationPointVente.objects.filter(
            employe=employe,
            point_vente=point_vente,
            role=role,
        ).exclude(id=affectation.id).exists()
        if duplicate:
            return JsonResponse({
                "success": False,
                "error": "Cette affectation existe déjà pour cet employé, ce POS et ce rôle.",
            }, status=400)
    else:
        affectation = AffectationPointVente(
            employe=employe,
            point_vente=point_vente,
            role=role,
        )

    affectation.employe = employe
    affectation.point_vente = point_vente
    affectation.role = role
    affectation.mode_acces = mode_acces
    affectation.date_debut = date_debut
    affectation.date_fin = date_fin
    affectation.principal = bool(data.get("principal", False))
    affectation.actif = bool(data.get("actif", True))

    permissions = data.get("permissions") or {}
    for field in PERMISSION_FIELDS:
        setattr(affectation, field, bool(permissions.get(field, False)))

    affectation.save()

    # TOTAL est une portée globale : le point de vente sert d'ancrage administratif,
    # mais le moteur applique ensuite l'autorisation à tous les Bar/Restaurant.
    if affectation.principal:
        AffectationPointVente.objects.filter(
            employe=employe,
            actif=True,
        ).exclude(id=affectation.id).update(principal=False)

    return JsonResponse({
        "success": True,
        "affectation": _serialize_affectation(
            AffectationPointVente.objects.select_related(
                "employe", "point_vente"
            ).prefetch_related("horaires").get(id=affectation.id)
        ),
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_acces_supprimer(request, affectation_id):
    if not _can_manage_access(request.user):
        return _forbidden()

    affectation = get_object_or_404(
        AffectationPointVente,
        id=affectation_id,
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )
    if affectation.shifts.exists():
        affectation.actif = False
        affectation.save(update_fields=["actif"])
        return JsonResponse({
            "success": True,
            "deleted": False,
            "disabled": True,
            "message": "Affectation désactivée car elle possède un historique de planning.",
        })

    affectation.delete()
    return JsonResponse({"success": True, "deleted": True})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_horaire_enregistrer(request, affectation_id):
    if not _can_manage_access(request.user):
        return _forbidden()

    import json
    data = json.loads(request.body or "{}")
    affectation = get_object_or_404(
        AffectationPointVente,
        id=affectation_id,
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )

    if affectation.mode_acces != ModeAccesPOS.HORAIRES:
        return JsonResponse({
            "success": False,
            "error": "Les horaires récurrents exigent le mode HORAIRES.",
        }, status=400)

    jour = int(data.get("jour_semaine"))
    if jour not in {value for value, _ in HoraireAffectation.JourSemaine.choices}:
        return JsonResponse({"success": False, "error": "Jour invalide."}, status=400)

    heure_debut = _parse_time(data.get("heure_debut"))
    heure_fin = _parse_time(data.get("heure_fin"))
    if not heure_debut or not heure_fin:
        return JsonResponse({
            "success": False,
            "error": "Heure de début et heure de fin obligatoires.",
        }, status=400)
    if heure_debut == heure_fin:
        return JsonResponse({
            "success": False,
            "error": "Début et fin doivent être différents.",
        }, status=400)

    date_debut = _parse_date(data.get("date_debut"))
    date_fin = _parse_date(data.get("date_fin"))
    if date_debut and date_fin and date_fin < date_debut:
        return JsonResponse({
            "success": False,
            "error": "La date de fin doit être postérieure à la date de début.",
        }, status=400)

    horaire_id = data.get("id")
    if horaire_id:
        horaire = get_object_or_404(
            HoraireAffectation,
            id=horaire_id,
            affectation=affectation,
        )
    else:
        horaire = HoraireAffectation(affectation=affectation)

    duplicate = HoraireAffectation.objects.filter(
        affectation=affectation,
        jour_semaine=jour,
        heure_debut=heure_debut,
        heure_fin=heure_fin,
    )
    if horaire.pk:
        duplicate = duplicate.exclude(pk=horaire.pk)
    if duplicate.exists():
        return JsonResponse({
            "success": False,
            "error": "Ce créneau existe déjà.",
        }, status=400)

    horaire.jour_semaine = jour
    horaire.heure_debut = heure_debut
    horaire.heure_fin = heure_fin
    horaire.date_debut = date_debut
    horaire.date_fin = date_fin
    horaire.actif = bool(data.get("actif", True))
    horaire.save()

    return JsonResponse({
        "success": True,
        "horaire": _serialize_horaire(horaire),
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_horaire_supprimer(request, affectation_id, horaire_id):
    if not _can_manage_access(request.user):
        return _forbidden()

    horaire = get_object_or_404(
        HoraireAffectation,
        id=horaire_id,
        affectation_id=affectation_id,
        affectation__point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )
    horaire.delete()
    return JsonResponse({"success": True})

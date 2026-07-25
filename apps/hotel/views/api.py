# apps/hotel/views/api.py
import json
from decimal import Decimal
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.db.models import Sum

from ..models import UniteModel
from ..models.reservations import Reservation
from ..models.sejours import Sejour


def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _money(value):
    return float(value or Decimal("0"))


@login_required
@require_GET
def api_stats(request):
    total_unites = UniteModel.objects.filter(actif=True).count()
    unites_disponibles = UniteModel.objects.filter(actif=True, statut="DISPONIBLE").count()
    unites_occupees = UniteModel.objects.filter(actif=True, statut="OCCUPEE").count()
    taux_occupation = round((unites_occupees / total_unites * 100), 1) if total_unites else 0
    
    from apps.facturation.models import LigneFactureModel
    
    mois_courant = date.today().month
    annee_courante = date.today().year
    
    lignes_mois = LigneFactureModel.objects.filter(
        facture__date_emission__year=annee_courante,
        facture__date_emission__month=mois_courant,
        facture__statut='PAYEE'
    )
    
    ca_mois = sum(l.total_ttc for l in lignes_mois)

    reservations_en_cours = Reservation.objects.filter(statut='CONFIRMEE').count()

    return JsonResponse({
        "success": True,
        "stats": {
            "total_unites": total_unites,
            "unites_disponibles": unites_disponibles,
            "unites_occupees": unites_occupees,
            "taux_occupation": taux_occupation,
            "locations_en_cours": reservations_en_cours,
            "ca_mois": float(ca_mois),
        },
    })


@login_required
@require_GET
def api_unites(request):
    unites = UniteModel.objects.filter(actif=True).order_by("type_unite", "code")

    type_chambre = request.GET.get("type_chambre")
    if type_chambre:
        unites = unites.filter(type_chambre_id=type_chambre)

    return JsonResponse({
        "success": True,
        "unites": [
            {
                "id": unite.id,
                "code": unite.code,
                "nom": unite.nom,
                "type_unite": unite.type_unite,
                "type_display": unite.get_type_unite_display(),
                "capacite": unite.capacite,
                "prix": _money(unite.prix),
                "statut": unite.statut,
                "image": unite.image.url if unite.image else None,
            }
            for unite in unites
        ],
    })


@login_required
@require_GET
def api_tarifs(request):
    chambre_id = request.GET.get("chambre")
    if not chambre_id:
        return JsonResponse({"success": False, "error": "Chambre requise"}, status=400)

    chambre = get_object_or_404(UniteModel, id=chambre_id)
    tarifs = chambre.tarifs.filter(actif=True)

    return JsonResponse({
        "success": True,
        "tarifs": [
            {
                "id": t.id,
                "nom": t.nom,
                "montant": float(t.montant),
            }
            for t in tarifs
        ],
    })

@login_required
@require_POST
def api_save_tarif(request):
    data = _payload(request)
    try:
        chambre = get_object_or_404(UniteModel, id=data.get("chambre_id"))
        tarif_id = data.get("tarif_id")
        nom = data.get("nom", "").strip()
        montant = Decimal(str(data.get("montant", 0)))
        
        if not nom or montant <= 0:
            return JsonResponse({"success": False, "error": "Nom et montant valides requis"}, status=400)
            
        if tarif_id:
            tarif = get_object_or_404(chambre.tarifs, id=tarif_id)
            tarif.nom = nom
            tarif.montant = montant
            tarif.save()
        else:
            tarif = chambre.tarifs.create(nom=nom, montant=montant)
            
        return JsonResponse({"success": True, "id": tarif.id})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)

@login_required
@require_POST
def api_supprimer_tarif(request, tarif_id):
    try:
        from ..models.tarifs import Tarif
        tarif = get_object_or_404(Tarif, id=tarif_id)
        tarif.delete()
        return JsonResponse({"success": True})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@require_POST
def api_save_unite(request):
    data = _payload(request)
    try:
        type_unite = data.get("type_unite") or "CHAMBRE"
        if type_unite not in ("CHAMBRE", "VIP"):
            return JsonResponse({"success": False, "error": "Type d'unité invalide."}, status=400)
        unite = UniteModel.objects.create(
            code=data.get("code", "").strip(),
            nom=data.get("nom", "").strip(),
            type_unite=type_unite,
            capacite=int(data.get("capacite") or 1),
            prix=Decimal(str(data.get("prix") or 0)),
            prix_jour=Decimal(str(data.get("prix_jour") or 0)),
        )
        return JsonResponse({"success": True, "id": unite.id})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@require_POST
def api_supprimer_unite(request, unite_id):
    try:
        unite = get_object_or_404(UniteModel, id=unite_id)
        unite.delete()
        return JsonResponse({"success": True})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@require_GET
def api_ca_evolution(request):
    from apps.facturation.models import LigneFactureModel
    
    today = date.today()
    start_date = today - timedelta(days=29)
    labels = []
    ca_data = []

    lignes = LigneFactureModel.objects.filter(
        facture__date_emission__gte=start_date,
        facture__statut='PAYEE'
    ).select_related('facture')

    # Grouper par jour
    ca_par_jour = {}
    for l in lignes:
        d = l.facture.date_emission
        if d not in ca_par_jour:
            ca_par_jour[d] = 0
        ca_par_jour[d] += float(l.total_ttc)

    for i in range(30):
        d = start_date + timedelta(days=i)
        labels.append(d.strftime("%d/%m"))
        ca_data.append(ca_par_jour.get(d, 0.0))

    return JsonResponse({
        "success": True,
        "labels": labels,
        "ca_data": ca_data,
    })

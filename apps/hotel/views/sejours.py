from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.utils import timezone
from datetime import timedelta

from ..models import Sejour, UniteModel, Client, TarifChambre, TypeChambre
from ..services.checkin_service import CheckInService
from ..services.checkout_service import CheckOutService
from ..services.disponibilite_service import DisponibiliteService
from ..services.tarification_service import TarificationService
from apps.entreprises.services import obtenir_etablissement_actuel


@login_required
def liste_sejours(request):
    etablissement = obtenir_etablissement_actuel()
    sejours = Sejour.objects.filter(
        etablissement=etablissement,
    ).select_related("client", "chambre", "cree_par").order_by("-date_arrivee")

    statut = request.GET.get("statut")
    if statut:
        sejours = sejours.filter(statut=statut)

    context = {
        "sejours": sejours,
        "statuts": Sejour.StatutSejour.choices,
        "filtre_statut": statut,
    }
    return render(request, "hotel/sejours/liste.html", context)


@login_required
def detail_sejour(request, sejour_id):
    sejour = get_object_or_404(
        Sejour.objects.select_related("client", "chambre", "reservation", "cree_par", "ferme_par"),
        id=sejour_id,
    )
    occupants = sejour.occupants.all()
    services = sejour.services.all()
    context = {
        "sejour": sejour,
        "occupants": occupants,
        "services": services,
    }
    return render(request, "hotel/sejours/detail.html", context)


@login_required
def check_in(request):
    etablissement = obtenir_etablissement_actuel()

    if request.method == "POST":
        client_id = request.POST.get("client")
        chambre_id = request.POST.get("chambre")
        tarif_id = request.POST.get("tarif")
        reservation_id = request.POST.get("reservation")
        notes = request.POST.get("notes", "")

        try:
            from ..models import Reservation
            if reservation_id:
                reservation = Reservation.objects.get(id=reservation_id)
                sejours = CheckInService.effectuer_check_in(
                    reservation=reservation,
                    utilisateur=request.user,
                    notes=notes,
                )
                messages.success(request, f"Check-in effectué pour {len(sejours)} chambre(s).")
            else:
                client = Client.objects.get(id=client_id)
                chambre = UniteModel.objects.get(id=chambre_id)
                tarif = TarifChambre.objects.select_related("type_tarif", "plan_tarifaire").get(id=tarif_id)
                sejour = CheckInService.check_in_sans_reservation(
                    etablissement=etablissement,
                    client=client,
                    chambre=chambre,
                    tarif=tarif,
                    utilisateur=request.user,
                    notes=notes,
                )
                messages.success(request, f"Check-in direct pour {sejour.code}.")
            return redirect("hotel:liste_sejours")
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    from ..models import Reservation
    aujourd_hui = timezone.now().date()
    date_arrivee = request.GET.get("date_arrivee", aujourd_hui.isoformat())
    date_depart = request.GET.get("date_depart", (aujourd_hui + timedelta(days=1)).isoformat())

    reservations_confirmees = Reservation.objects.filter(
        etablissement=etablissement,
        statut=Reservation.StatutReservation.CONFIRMEE,
    ).select_related("client").order_by("date_arrivee_prevue")

    chambres_disponibles = DisponibiliteService.chambres_disponibles(
        etablissement=etablissement,
        date_arrivee=date_arrivee,
        date_depart=date_depart,
    )

    context = {
        "reservations": reservations_confirmees,
        "chambres": chambres_disponibles,
        "types_chambres": TypeChambre.objects.filter(actif=True),
        "clients": Client.objects.filter(statut="ACTIF").order_by("nom"),
    }
    return render(request, "hotel/sejours/check_in.html", context)


@login_required
def check_out(request, sejour_id):
    sejour = get_object_or_404(Sejour.objects.select_related("chambre", "client"), id=sejour_id)

    if request.method == "POST":
        notes = request.POST.get("notes", "")
        try:
            CheckOutService.effectuer_check_out(
                sejour=sejour,
                utilisateur=request.user,
                notes=notes,
            )
            messages.success(request, f"Check-out effectué pour {sejour.code}.")
            return redirect("hotel:detail_sejour", sejour_id=sejour.id)
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    context = {
        "sejour": sejour,
        "tarifs_possibles": TarifChambre.objects.filter(
            type_chambre=sejour.chambre.type_chambre,
            actif=True,
        ).select_related("type_tarif", "plan_tarifaire") if sejour.chambre.type_chambre else [],
    }
    return render(request, "hotel/sejours/check_out.html", context)


@login_required
def cloturer_sejour(request, sejour_id):
    sejour = get_object_or_404(Sejour, id=sejour_id)
    try:
        CheckOutService.cloturer(sejour=sejour, utilisateur=request.user)
        messages.success(request, f"Séjour {sejour.code} clôturé.")
    except Exception as e:
        messages.error(request, f"Erreur : {e}")
    return redirect("hotel:detail_sejour", sejour_id=sejour.id)

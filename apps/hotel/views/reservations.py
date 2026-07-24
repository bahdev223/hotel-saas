from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction

from ..models import Reservation, ReservationChambre, UniteModel, TypeChambre, TarifChambre, Client
from ..services.reservation_service import ReservationService
from ..services.tarification_service import TarificationService
from ..services.disponibilite_service import DisponibiliteService
from apps.entreprises.services import obtenir_etablissement_actuel


@login_required
def liste_reservations(request):
    etablissement = obtenir_etablissement_actuel()
    reservations = Reservation.objects.filter(
        etablissement=etablissement,
    ).select_related("client", "cree_par").order_by("-date_arrivee_prevue")

    statut = request.GET.get("statut")
    if statut:
        reservations = reservations.filter(statut=statut)

    context = {
        "reservations": reservations,
        "statuts": Reservation.StatutReservation.choices,
        "filtre_statut": statut,
    }
    return render(request, "hotel/reservations/liste.html", context)


@login_required
def detail_reservation(request, reservation_id):
    reservation = get_object_or_404(
        Reservation.objects.select_related("client", "cree_par"),
        id=reservation_id,
    )
    chambres = reservation.chambres_reservees.select_related("chambre", "tarif_source", "tarif_source__type_tarif")
    context = {
        "reservation": reservation,
        "chambres": chambres,
    }
    return render(request, "hotel/reservations/detail.html", context)


@login_required
def ajouter_reservation(request):
    etablissement = obtenir_etablissement_actuel()

    if request.method == "POST":
        client_id = request.POST.get("client")
        chambre_id = request.POST.get("chambre")
        tarif_id = request.POST.get("tarif")
        date_arrivee = request.POST.get("date_arrivee_prevue")
        date_depart = request.POST.get("date_depart_prevue")
        adultes = request.POST.get("nombre_adultes", 1)
        enfants = request.POST.get("nombre_enfants", 0)
        notes = request.POST.get("notes", "")

        try:
            client = Client.objects.get(id=client_id)
            chambre = UniteModel.objects.get(id=chambre_id)
            tarif = TarifChambre.objects.select_related("type_tarif", "plan_tarifaire").get(id=tarif_id)

            reservation = ReservationService.creer_reservation(
                etablissement=etablissement,
                client=client,
                date_arrivee_prevue=date_arrivee,
                date_depart_prevue=date_depart,
                chambre=chambre,
                tarif=tarif,
                utilisateur=request.user,
                nombre_adultes=int(adultes),
                nombre_enfants=int(enfants),
                notes=notes,
            )
            messages.success(request, f"Réservation {reservation.code} créée.")
            return redirect("hotel:detail_reservation", reservation_id=reservation.id)
        except Exception as e:
            messages.error(request, f"Erreur : {e}")

    types_chambres = TypeChambre.objects.filter(actif=True)
    context = {
        "types_chambres": types_chambres,
        "clients": Client.objects.filter(statut="ACTIF").order_by("nom"),
    }
    return render(request, "hotel/reservations/ajouter.html", context)


@login_required
def annuler_reservation(request, reservation_id):
    reservation = get_object_or_404(Reservation, id=reservation_id)

    if request.method == "POST":
        motif = request.POST.get("motif", "")
        try:
            ReservationService.annuler_reservation(
                reservation=reservation,
                motif=motif,
                utilisateur=request.user,
            )
            messages.success(request, f"Réservation {reservation.code} annulée.")
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
        return redirect("hotel:detail_reservation", reservation_id=reservation.id)

    return render(request, "hotel/reservations/annuler.html", {"reservation": reservation})

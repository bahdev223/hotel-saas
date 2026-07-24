from django.db import models as db_models
from django.utils import timezone

from ..models import Reservation, ReservationChambre, UniteModel, Sejour
from ..models.reservations import Reservation as ReservationModel
from ..models.sejours import Sejour as SejourModel
from ..models.unite import StatutChambre


class DisponibiliteService:
    @classmethod
    def chambres_disponibles(cls, *, etablissement, date_arrivee, date_depart, type_chambre=None):
        if date_arrivee >= date_depart:
            return UniteModel.objects.none()

        chambres = UniteModel.objects.filter(
            actif=True,
            statut__in=[
                StatutChambre.DISPONIBLE,
                StatutChambre.RESERVEE,
                StatutChambre.A_NETTOYER,
            ],
        )

        if type_chambre:
            chambres = chambres.filter(type_chambre=type_chambre)

        ids_conflits_reservation = ReservationChambre.objects.filter(
            chambre__in=chambres,
            reservation__statut__in=[
                ReservationModel.StatutReservation.CONFIRMEE,
                ReservationModel.StatutReservation.EN_ATTENTE,
            ],
            reservation__date_arrivee_prevue__lt=date_depart,
            reservation__date_depart_prevue__gt=date_arrivee,
        ).values_list("chambre_id", flat=True)

        ids_conflits_sejour = SejourModel.objects.filter(
            chambre__in=chambres,
            statut__in=[
                SejourModel.StatutSejour.EN_COURS,
                SejourModel.StatutSejour.CHECK_IN,
                SejourModel.StatutSejour.PROLONGE,
                SejourModel.StatutSejour.PREVU,
            ],
            date_arrivee__lt=date_depart,
            date_depart__gt=date_arrivee,
        ).values_list("chambre_id", flat=True)

        ids_exclus = set(ids_conflits_reservation) | set(ids_conflits_sejour)
        return chambres.exclude(id__in=ids_exclus)

    @classmethod
    def sejours_actifs(cls, *, etablissement):
        return SejourModel.objects.filter(
            etablissement=etablissement,
            statut__in=[
                SejourModel.StatutSejour.EN_COURS,
                SejourModel.StatutSejour.CHECK_IN,
                SejourModel.StatutSejour.PROLONGE,
            ],
        ).select_related("chambre", "client").order_by("-date_arrivee")

    @classmethod
    def occupancies_aujourdhui(cls, *, etablissement):
        aujourd_hui = timezone.now().date()
        return {
            "total": UniteModel.objects.filter(actif=True).count(),
            "occupees": UniteModel.objects.filter(
                statut=StatutChambre.OCCUPEE,
            ).count(),
            "disponibles": UniteModel.objects.filter(
                statut=StatutChambre.DISPONIBLE,
            ).count(),
            "en_nettoyage": UniteModel.objects.filter(
                statut__in=[StatutChambre.A_NETTOYER, StatutChambre.NETTOYAGE],
            ).count(),
            "maintenance": UniteModel.objects.filter(
                statut__in=[StatutChambre.MAINTENANCE, StatutChambre.HORS_SERVICE],
            ).count(),
            "reservees": UniteModel.objects.filter(
                statut=StatutChambre.RESERVEE,
            ).count(),
        }

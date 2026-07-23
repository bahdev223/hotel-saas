from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models import Sejour, Reservation, UniteModel
from ..models.unite import StatutChambre
from ..models.sejours import Sejour as SejourModel


class CheckInService:
    @classmethod
    @transaction.atomic
    def effectuer_check_in(cls, *, reservation, utilisateur, notes=""):
        if reservation.statut not in (Reservation.StatutReservation.CONFIRMEE, Reservation.StatutReservation.PARTIELLEMENT_PAYEE):
            raise ValidationError("Seule une réservation confirmée peut faire l'objet d'un check-in.")

        if reservation.chambres_reservees.count() == 0:
            raise ValidationError("Aucune chambre associée à cette réservation.")

        sejours = []
        for rc in reservation.chambres_reservees.all():
            chambre = rc.chambre
            if chambre.statut not in (StatutChambre.DISPONIBLE, StatutChambre.RESERVEE):
                raise ValidationError(f"La chambre {chambre.code} n'est pas disponible.")

            sejour = SejourModel.objects.create(
                etablissement=reservation.etablissement,
                reservation=reservation,
                client=reservation.client,
                chambre=chambre,
                date_arrivee=timezone.now(),
                nombre_adultes=reservation.nombre_adultes,
                nombre_enfants=reservation.nombre_enfants,
                montant_base=rc.montant_total,
                montant_total=rc.montant_total,
                statut=SejourModel.StatutSejour.EN_COURS,
                notes=notes,
                cree_par=utilisateur,
            )
            sejours.append(sejour)

            chambre.occuper()

        reservation.statut = Reservation.StatutReservation.TRANSFORMEE
        reservation.save(update_fields=["statut"])

        return sejours

    @classmethod
    @transaction.atomic
    def check_in_sans_reservation(
        cls,
        *,
        etablissement,
        client,
        chambre,
        tarif,
        utilisateur,
        date_arrivee=None,
        nombre_adultes=1,
        nombre_enfants=0,
        notes="",
    ):
        from ..services.tarification_service import TarificationService
        from decimal import Decimal

        if date_arrivee is None:
            date_arrivee = timezone.now()
        date_depart = date_arrivee + timezone.timedelta(days=1)

        if chambre.statut not in (StatutChambre.DISPONIBLE, StatutChambre.RESERVEE):
            raise ValidationError("La chambre n'est pas disponible.")

        montant = TarificationService.calculer_montant(
            tarif=tarif,
            date_debut=date_arrivee,
            date_fin=date_depart,
            nombre_adultes=nombre_adultes,
            nombre_enfants=nombre_enfants,
        )

        sejour = SejourModel.objects.create(
            etablissement=etablissement,
            client=client,
            chambre=chambre,
            date_arrivee=date_arrivee,
            nombre_adultes=nombre_adultes,
            nombre_enfants=nombre_enfants,
            montant_base=montant,
            montant_total=montant,
            statut=SejourModel.StatutSejour.EN_COURS,
            notes=notes,
            cree_par=utilisateur,
        )

        chambre.occuper()
        return sejour

from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError

from ..models import Reservation, ReservationChambre, UniteModel
from .tarification_service import TarificationService
from ..models.unite import StatutChambre
from ..models.tarifs import TarifChambre
from django.db.models import Q


class ReservationService:
    @classmethod
    @transaction.atomic
    def creer_reservation(
        cls,
        *,
        etablissement,
        client,
        date_arrivee_prevue,
        date_depart_prevue,
        chambre,
        tarif,
        utilisateur,
        nombre_adultes=1,
        nombre_enfants=0,
        notes="",
    ):
        if date_arrivee_prevue >= date_depart_prevue:
            raise ValidationError("La date d'arrivée doit être antérieure à la date de départ.")

        chambre = UniteModel.objects.select_for_update().get(id=chambre.id)

        if not cls._chambre_disponible(chambre, date_arrivee_prevue, date_depart_prevue):
            raise ValidationError("La chambre n'est pas disponible pour cette période.")

        quantite = cls._calculer_quantite(tarif, date_arrivee_prevue, date_depart_prevue)
        montant_total = TarificationService.calculer_montant(
            tarif=tarif,
            date_debut=date_arrivee_prevue,
            date_fin=date_depart_prevue,
            nombre_adultes=nombre_adultes,
            nombre_enfants=nombre_enfants,
        )

        reservation = Reservation.objects.create(
            etablissement=etablissement,
            client=client,
            date_arrivee_prevue=date_arrivee_prevue,
            date_depart_prevue=date_depart_prevue,
            nombre_adultes=nombre_adultes,
            nombre_enfants=nombre_enfants,
            montant_total_estime=montant_total,
            notes=notes,
            cree_par=utilisateur,
        )

        ReservationChambre.objects.create(
            reservation=reservation,
            chambre=chambre,
            tarif_source=tarif,
            type_tarif_nom=tarif.type_tarif.nom,
            plan_tarifaire_nom=tarif.plan_tarifaire.nom,
            montant_unitaire=tarif.montant,
            quantite=quantite,
            montant_total=montant_total,
        )

        chambre.reserver()

        return reservation

    @classmethod
    @transaction.atomic
    def confirmer_reservation(cls, *, reservation, utilisateur):
        if reservation.statut not in (Reservation.StatutReservation.BROUILLON, Reservation.StatutReservation.EN_ATTENTE, Reservation.StatutReservation.OPTION):
            raise ValidationError("Seules les réservations en brouillon, en attente ou option peuvent être confirmées.")

        reservation.statut = Reservation.StatutReservation.CONFIRMEE
        reservation.save(update_fields=["statut"])
        return reservation

    @classmethod
    @transaction.atomic
    def annuler_reservation(cls, *, reservation, motif, utilisateur):
        if not reservation.est_annulable:
            raise ValidationError("Cette réservation ne peut plus être annulée.")

        reservation.statut = Reservation.StatutReservation.ANNULEE
        reservation.motif_annulation = motif
        reservation.annule_par = utilisateur
        reservation.annule_le = timezone.now()
        reservation.save(update_fields=["statut", "motif_annulation", "annule_par", "annule_le"])

        for rc in reservation.chambres_reservees.all():
            rc.chambre.liberer()

        return reservation

    @classmethod
    def _chambre_disponible(cls, chambre, arrivee, depart):
        conflits = ReservationChambre.objects.filter(
            chambre=chambre,
            reservation__statut__in=[
                Reservation.StatutReservation.CONFIRMEE,
                Reservation.StatutReservation.EN_ATTENTE,
                Reservation.StatutReservation.OPTION,
            ],
            reservation__date_arrivee_prevue__lt=depart,
            reservation__date_depart_prevue__gt=arrivee,
        )
        sejours_actifs = chambre.sejours.filter(
            statut__in=["CHECK_IN", "EN_COURS", "PROLONGE"],
            date_arrivee__lt=depart,
            date_depart__gt=arrivee,
        )
        return not conflits.exists() and not sejours_actifs.exists()

    @classmethod
    def _calculer_quantite(cls, tarif, debut, fin):
        if tarif.type_tarif.unite_facturation == "NUITEE":
            return max(1, (fin.date() - debut.date()).days)
        elif tarif.type_tarif.unite_facturation == "HEURE":
            return max(1, int((fin - debut).total_seconds() / 3600))
        elif tarif.type_tarif.unite_facturation == "JOURNEE":
            return max(1, (fin.date() - debut.date()).days)
        elif tarif.type_tarif.unite_facturation == "DEMI_JOURNEE":
            return 1
        elif tarif.type_tarif.unite_facturation == "FORFAIT":
            return 1
        else:
            return 1

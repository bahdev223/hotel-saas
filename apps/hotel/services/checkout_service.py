from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

from ..models import Sejour, ServiceSejour, UniteModel
from ..models.sejours import Sejour as SejourModel
from ..models.unite import StatutChambre
from ..services.tarification_service import TarificationService


class CheckOutService:
    @classmethod
    @transaction.atomic
    def effectuer_check_out(cls, *, sejour, utilisateur, notes=""):
        if not sejour.est_actif:
            raise ValidationError("Ce séjour n'est pas actif.")

        date_depart = timezone.now()
        sejour.date_depart = date_depart
        sejour.statut = SejourModel.StatutSejour.CHECK_OUT
        sejour.ferme_par = utilisateur
        sejour.notes = (sejour.notes or "") + ("\n" + notes if notes else "")
        sejour.save(update_fields=["date_depart", "statut", "ferme_par", "notes"])

        cls._recalculer_montant(sejour)

        sejour.chambre.liberer()

        return sejour

    @classmethod
    @transaction.atomic
    def cloturer(cls, *, sejour, utilisateur):
        if sejour.statut != SejourModel.StatutSejour.CHECK_OUT:
            raise ValidationError("Le séjour doit d'abord être en check-out avant d'être clôturé.")

        sejour.statut = SejourModel.StatutSejour.CLOTURE
        sejour.save(update_fields=["statut"])
        return sejour

    @classmethod
    def _recalculer_montant(cls, sejour):
        from ..models.tarifs import TarifChambre, TypeTarif

        nuits = sejour.duree_nuits
        if nuits > 1 and sejour.reservation:
            rc = sejour.reservation.chambres_reservees.filter(chambre=sejour.chambre).first()
            if rc:
                sejour.montant_base = rc.montant_unitaire * Decimal(str(nuits))
                sejour.montant_total = sejour.montant_base + sejour.montant_supplements
                sejour.save(update_fields=["montant_base", "montant_total"])

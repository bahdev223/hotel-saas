from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal

from ..models import Sejour


class CheckOutService:
    @classmethod
    @transaction.atomic
    def effectuer_check_out(cls, *, sejour, utilisateur, notes=""):
        if not sejour.est_actif:
            raise ValidationError("Ce séjour n'est pas actif.")

        date_depart = timezone.now()
        sejour.date_depart = date_depart
        sejour.statut = Sejour.StatutSejour.CHECK_OUT
        sejour.ferme_par = utilisateur
        sejour.notes = (sejour.notes or "") + ("\n" + notes if notes else "")
        sejour.save(update_fields=["date_depart", "statut", "ferme_par", "notes"])

        cls._recalculer_montant(sejour)
        cls._creer_facture(sejour, utilisateur)

        sejour.chambre.liberer()

        return sejour

    @classmethod
    @transaction.atomic
    def cloturer(cls, *, sejour, utilisateur):
        if sejour.statut != Sejour.StatutSejour.CHECK_OUT:
            raise ValidationError("Le séjour doit d'abord être en check-out avant d'être clôturé.")

        sejour.statut = Sejour.StatutSejour.CLOTURE
        sejour.save(update_fields=["statut"])
        return sejour

    @classmethod
    def _aggreger_supplements(cls, sejour):
        total = Decimal("0")
        for service in sejour.services.all():
            total += service.montant
        if sejour.montant_supplements != total:
            sejour.montant_supplements = total
            sejour.save(update_fields=["montant_supplements"])
        return total

    @classmethod
    def _recalculer_montant(cls, sejour):
        cls._aggreger_supplements(sejour)

        nuits = sejour.duree_nuits
        rc = None
        if sejour.reservation:
            rc = sejour.reservation.chambres_reservees.filter(chambre=sejour.chambre).first()

        if rc and nuits > 1:
            sejour.montant_base = rc.montant_unitaire * Decimal(str(nuits))
        elif rc and nuits == 1:
            sejour.montant_base = rc.montant_unitaire
        elif not rc and sejour.montant_base == 0:
            from ..models.tarifs import TarifChambre
            tarif = TarifChambre.objects.filter(type_chambre=sejour.chambre.type_chambre, actif=True).first()
            if tarif:
                sejour.montant_base = tarif.montant * Decimal(str(nuits))

        sejour.montant_total = sejour.montant_base + sejour.montant_supplements
        sejour.save(update_fields=["montant_base", "montant_total"])

    @classmethod
    @transaction.atomic
    def _creer_facture(cls, sejour, utilisateur):
        from apps.facturation.models import FactureModel, LigneFactureModel

        if hasattr(sejour, 'facture') and sejour.facture:
            return sejour.facture

        facture = FactureModel.objects.create(
            sejour=sejour,
            client=sejour.client,
            client_nom=sejour.client.nom_complet if hasattr(sejour.client, 'nom_complet') else str(sejour.client),
            client_contact=getattr(sejour.client, 'telephone', ''),
            statut='EMISE',
        )

        LigneFactureModel.objects.create(
            facture=facture,
            description=f"Séjour {sejour.code} - {sejour.chambre} ({sejour.date_arrivee.date()} au {sejour.date_depart.date()}) - {sejour.duree_nuits} nuit(s)",
            quantite=sejour.duree_nuits,
            prix_unitaire=sejour.montant_base / sejour.duree_nuits if sejour.duree_nuits > 0 else sejour.montant_base,
        )

        for service in sejour.services.all():
            LigneFactureModel.objects.create(
                facture=facture,
                description=service.libelle or f"Supplément - {service.service}",
                quantite=1,
                prix_unitaire=service.montant,
            )

        return facture

from decimal import Decimal
from datetime import date
from django.db import models

from ..models.tarifs import Tarif
from ..models.unite import UniteModel


class TarificationService:
    @classmethod
    def calculer_montant(cls, *, tarif, quantite):
        """
        Calcule le montant total en multipliant le montant du tarif par la quantité.
        (ex: 1 Nuitée x 15000 = 15000, 2 Heures x 5000 = 10000)
        """
        return tarif.montant * Decimal(str(quantite))

    @classmethod
    def calculer_nuits(cls, *, date_debut, date_fin):
        """Nombre de nuits entre deux dates (minimum 1)."""
        return max(1, (date_fin.date() - date_debut.date()).days)

    @classmethod
    def calculer_montant_sejour(cls, *, tarif, date_debut, date_fin):
        """
        Le tarif d'une chambre est un prix par nuit : calcule le montant total
        du séjour en le multipliant par le nombre de nuits entre les deux dates.
        """
        nuits = cls.calculer_nuits(date_debut=date_debut, date_fin=date_fin)
        return cls.calculer_montant(tarif=tarif, quantite=nuits)

    @classmethod
    def appliquer_tarif(cls, *, reservation, chambre, tarif, quantite, utilisateur=None):
        """
        Retourne un dictionnaire contenant les valeurs à appliquer sur une ReservationChambre.
        """
        return {
            "tarif_source": tarif,
            "tarif_nom": tarif.nom,
            "montant_unitaire": tarif.montant,
            "quantite": quantite,
            "montant_total": cls.calculer_montant(tarif=tarif, quantite=quantite),
        }

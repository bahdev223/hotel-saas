# apps/stock/services/politique_stock_service.py
from decimal import Decimal
from ..models.politique_stock import PolitiqueStockRestaurant


class PolitiqueStockService:
    """Service de résolution des PolitiqueStockRestaurant.

    Résout la politique applicable dans l'ordre de priorité :
      1. point_vente spécifique
      2. etablissement du point_vente
      3. politique par défaut (etablissement=None, point_vente=None)
    """

    @staticmethod
    def get_politique(point_vente=None):
        if point_vente:
            p = PolitiqueStockRestaurant.objects.filter(
                point_vente=point_vente, actif=True
            ).first()
            if p:
                return p
            etablissement = getattr(point_vente, 'etablissement', None)
            if etablissement:
                p = PolitiqueStockRestaurant.objects.filter(
                    etablissement=etablissement, point_vente__isnull=True, actif=True
                ).first()
                if p:
                    return p
        return PolitiqueStockRestaurant.objects.filter(
            etablissement__isnull=True, point_vente__isnull=True, actif=True
        ).first()

    @staticmethod
    def doit_consommer(point_vente=None):
        """Détermine si la consommation doit être déclenchée immédiatement."""
        politique = PolitiqueStockService.get_politique(point_vente)
        if not politique:
            return True
        return politique.evenement_declencheur == 'PAIEMENT'

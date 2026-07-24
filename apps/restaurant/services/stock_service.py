# apps/restaurant/services/stock_service.py
from django.db import transaction
from decimal import Decimal
from apps.stock.models import Produit, StockEntrepot, MouvementStock, Entrepot


class StockService:
    """Service de gestion des stocks pour le restaurant"""

    @staticmethod
    def get_stock_entrepot(produit, entrepot):
        stock = StockEntrepot.objects.filter(
            entrepot=entrepot,
            produit=produit
        ).first()
        return stock.quantite if stock else Decimal('0')

    @staticmethod
    @transaction.atomic
    def consommer_ingredient(produit, entrepot, quantite, utilisateur, reference="", raison=""):
        from apps.stock.services.mouvement_service import MouvementStockService

        MouvementStockService.sortie_stock(
            produit=produit,
            entrepot=entrepot,
            quantite=quantite,
            utilisateur=utilisateur,
            motif='consommation',
            reference=reference,
            raison=raison,
        )

    @staticmethod
    @transaction.atomic
    def ajouter_stock(produit, entrepot, quantite, utilisateur, reference="", raison=""):
        from apps.stock.services.mouvement_service import MouvementStockService

        MouvementStockService.entree_stock(
            produit=produit,
            entrepot=entrepot,
            quantite=quantite,
            utilisateur=utilisateur,
            motif='ajustement',
            reference=reference,
            raison=raison,
        )

    @staticmethod
    def transferer_stock(produit, source_entrepot, dest_entrepot, quantite, utilisateur, reference=""):
        from apps.stock.services.transfert_service import TransfertService

        return TransfertService.transfert_entre_entrepots(
            produit_id=produit.id,
            quantite=quantite,
            entrepot_source_id=source_entrepot.id,
            entrepot_dest_id=dest_entrepot.id,
            utilisateur=utilisateur,
            reference=reference
        )

    @staticmethod
    def get_produits_alertes(entrepot):
        stocks = StockEntrepot.objects.filter(
            entrepot=entrepot,
            quantite__lte=models.F('produit__seuil_alerte'),
            quantite__gt=0
        ).select_related('produit')

        return [
            {
                'produit': s.produit,
                'stock': s.quantite,
                'seuil': s.produit.seuil_alerte
            }
            for s in stocks
        ]

    @staticmethod
    def get_produits_rupture(entrepot):
        stocks = StockEntrepot.objects.filter(
            entrepot=entrepot,
            quantite__lte=0
        ).select_related('produit')

        return [s.produit for s in stocks]

from decimal import Decimal
from django.db import models
from apps.stock.models import Produit, Entrepot

class ValorisationStockService:
    """Service de valorisation des stocks (CUMP, etc.)"""

    @classmethod
    def get_cout_sortie(
        cls,
        *,
        produit: Produit,
        entrepot: Entrepot,
        quantite: Decimal,
    ) -> Decimal:
        if produit.methode_valorisation == "FIFO":
            return cls._cout_fifo(produit=produit, entrepot=entrepot, quantite=quantite)
        
        if produit.methode_valorisation == "STANDARD":
            return Decimal(str(produit.prix_achat)) # Simulé comme coût standard

        return cls._cout_cump(produit=produit, entrepot=entrepot)

    @classmethod
    def _cout_cump(cls, *, produit: Produit, entrepot: Entrepot) -> Decimal:
        """Calcule le Coût Unitaire Moyen Pondéré pour ce produit/entrepôt"""
        from apps.stock.models import StockEntrepot
        
        stock = StockEntrepot.objects.filter(
            produit=produit,
            entrepot=entrepot
        ).first()
        
        if stock and stock.prix_achat:
            return Decimal(str(stock.prix_achat))
            
        return Decimal(str(produit.prix_achat))

    @classmethod
    def _cout_fifo(cls, *, produit: Produit, entrepot: Entrepot, quantite: Decimal) -> Decimal:
        # A implémenter plus tard (nécessite les lots)
        return Decimal(str(produit.prix_achat))

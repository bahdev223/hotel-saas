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
            raise NotImplementedError("La valorisation FIFO n'est pas encore disponible.")
        
        if produit.methode_valorisation == "STANDARD":
            raise NotImplementedError("La valorisation STANDARD n'est pas encore disponible.")

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
    def calculer_cump_apres_entree(cls, stock, stock_avant: Decimal, quantite_entree: Decimal, cout_entree: Decimal) -> Decimal:
        """
        Calcule le nouveau CUMP après une entrée en stock.
        """
        cump_actuel = stock.prix_achat or Decimal('0')
        
        valeur_stock_actuel = stock_avant * cump_actuel
        valeur_entree = quantite_entree * cout_entree
        
        nouvelle_quantite_totale = stock_avant + quantite_entree
        if nouvelle_quantite_totale > 0:
            nouveau_cump = (valeur_stock_actuel + valeur_entree) / nouvelle_quantite_totale
            # On arrondit à 4 décimales (selon la nouvelle norme)
            return round(nouveau_cump, 4)
        return cout_entree

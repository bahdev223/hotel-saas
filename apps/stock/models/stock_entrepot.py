from django.db import models
from .entrepot import Entrepot
from .produit import Produit


class StockEntrepot(models.Model):
    """ Stock actuel dans chaque entrepôt """
    
    entrepot = models.ForeignKey(Entrepot, on_delete=models.CASCADE, related_name='stocks')
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='stocks_entrepots')
    quantite = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prix_achat = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Prix d'achat unitaire")
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock_entrepots_stock'
        verbose_name = 'Stock entrepôt'
        verbose_name_plural = 'Stocks entrepôts'
        unique_together = ['entrepot', 'produit']
    
    def __str__(self):
        return f"{self.entrepot.nom} - {self.produit.nom}: {self.quantite}"

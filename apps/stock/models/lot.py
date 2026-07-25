# apps/stock/models/lot.py
from django.db import models
from decimal import Decimal
from .produit import Produit
from .fournisseur import Fournisseur
from .entrepot import Entrepot

class LotProduit(models.Model):
    """Informations de base d'un lot physique, indépendant de l'entrepôt."""
    
    produit = models.ForeignKey(Produit, on_delete=models.PROTECT, related_name='lots_produit')
    numero = models.CharField(max_length=50, help_text="Numéro du lot")
    date_fabrication = models.DateField(null=True, blank=True)
    date_peremption = models.DateField(null=True, blank=True)
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.SET_NULL, null=True, blank=True)
    date_creation = models.DateTimeField(auto_now_add=True)
    actif = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'stock_lot_produit'
        verbose_name = 'Lot Produit'
        verbose_name_plural = 'Lots Produits'
        unique_together = ['produit', 'numero']
        ordering = ['date_peremption', '-date_creation']
    
    def __str__(self):
        return f"Lot {self.numero} - {self.produit.nom}"
        
    @property
    def est_perime(self):
        from datetime import date
        if not self.date_peremption:
            return False
        return self.date_peremption < date.today()
    
    @property
    def jours_restants(self):
        from datetime import date
        if not self.date_peremption:
            return -1
        delta = self.date_peremption - date.today()
        return max(0, delta.days)


class StockLotEntrepot(models.Model):
    """Quantité disponible d'un lot dans un entrepôt spécifique."""
    
    lot = models.ForeignKey(LotProduit, on_delete=models.PROTECT, related_name='stocks_entrepot')
    entrepot = models.ForeignKey(Entrepot, on_delete=models.PROTECT, related_name='stocks_lots')
    quantite = models.DecimalField(max_digits=18, decimal_places=4, default=0)
    
    class Meta:
        db_table = 'stock_stock_lot_entrepot'
        verbose_name = 'Stock Lot Entrepôt'
        verbose_name_plural = 'Stocks Lots Entrepôts'
        unique_together = ['lot', 'entrepot']
        
    def __str__(self):
        return f"{self.lot.numero} dans {self.entrepot.nom} : {self.quantite}"
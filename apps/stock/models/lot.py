# apps/stock/models/lot.py
from django.db import models
from decimal import Decimal
from .produit import Produit
from .fournisseur import Fournisseur


class Lot(models.Model):
    """Lot de produit avec traçabilité et date de péremption"""
    
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='lots')
    numero = models.CharField(max_length=50, help_text="Numéro du lot")
    quantite = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    quantite_restante = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_entree = models.DateTimeField(auto_now_add=True)
    date_peremption = models.DateField(null=True, blank=True)
    fournisseur = models.ForeignKey(Fournisseur, on_delete=models.SET_NULL, null=True, blank=True)
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actif = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'stock_lots'
        verbose_name = 'Lot'
        verbose_name_plural = 'Lots'
        unique_together = ['produit', 'numero']
        ordering = ['date_peremption', '-date_entree']
    
    def __str__(self):
        return f"Lot {self.numero} - {self.produit.nom} ({self.quantite_restante}/{self.quantite})"
    
    @property
    def est_perime(self):
        from datetime import date
        if not self.date_peremption:
            return False
        return self.date_peremption < date.today()
    
    @property
    def expire_bientot(self, jours=30):
        from datetime import date, timedelta
        if not self.date_peremption:
            return False
        return self.date_peremption <= date.today() + timedelta(days=jours)
    
    @property
    def jours_restants(self):
        from datetime import date
        if not self.date_peremption:
            return -1
        delta = self.date_peremption - date.today()
        return max(0, delta.days)
    
    def consommer(self, quantite):
        """Consomme une quantité du lot (FIFO)"""
        quantite = Decimal(str(quantite))
        if quantite > self.quantite_restante:
            raise ValueError(f"Stock insuffisant dans le lot {self.numero}")
        self.quantite_restante -= quantite
        self.save()
        return quantite
    
    def ajouter(self, quantite):
        """Ajoute une quantité au lot"""
        quantite = Decimal(str(quantite))
        self.quantite += quantite
        self.quantite_restante += quantite
        self.save()
        return quantite
    
    
# apps/stock/models/sous_unite.py
from django.db import models
from .produit import Produit


class SousUnite(models.Model):
    """Sous-unité pour un produit (ex: 1 caisse = 24 bouteilles)"""
    
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='sous_unites')
    nom = models.CharField(max_length=50, help_text="Ex: Caisse, Pack, Carton")
    facteur = models.DecimalField(max_digits=10, decimal_places=2, help_text="Nombre d'unités dans cette sous-unité")
    prix = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Prix spécifique (optionnel)")
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock_sous_unites'
        verbose_name = 'Sous-unité'
        verbose_name_plural = 'Sous-unités'
        unique_together = ['produit', 'nom']
        ordering = ['produit__nom', 'nom']
    
    def __str__(self):
        return f"{self.produit.nom} - {self.nom} (x{self.facteur})"
    
    @property
    def prix_reel(self):
        if self.prix and self.prix > 0:
            return self.prix
        return self.produit.prix_vente * self.facteur
    
    
    
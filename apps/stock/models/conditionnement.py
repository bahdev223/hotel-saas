from django.db import models
from .produit import Produit
from .unite import UniteMesure

class Conditionnement(models.Model):
    """Emballage ou format d'achat spécifique à un produit (ex: Caisse de 24 pour Produit A)"""
    
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='conditionnements')
    nom = models.CharField(max_length=100, help_text="Ex: Caisse, Carton, Palette")
    unite_destination = models.ForeignKey(UniteMesure, on_delete=models.PROTECT, related_name='+')
    facteur = models.DecimalField(
        max_digits=18, decimal_places=6,
        help_text="Nombre d'unités de destination dans ce conditionnement (ex: 1 Caisse = 24 Pièces -> Facteur=24)"
    )
    code_barre = models.CharField(max_length=100, unique=True, blank=True, null=True)
    
    class Meta:
        db_table = 'stock_conditionnement'
        verbose_name = 'Conditionnement'
        verbose_name_plural = 'Conditionnements'
        unique_together = ['produit', 'nom']
        
    def __str__(self):
        return f"{self.nom} de {self.produit.nom} ({self.facteur} {self.unite_destination.symbole})"

# apps/comptabilite/models/compte_tiers.py

from django.db import models
from .exercice import ExerciceModel
from .tiers import TiersModel  # ⚠️ adapte si ton fichier s'appelle autrement


class CompteTiersModel(models.Model):
    """Solde des comptes de tiers (clients, fournisseurs, etc.)"""
    
    tiers = models.ForeignKey(TiersModel, on_delete=models.CASCADE)
    exercice = models.ForeignKey(ExerciceModel, on_delete=models.CASCADE)
    
    solde = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ecart_lettrage = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compta_comptes_tiers'
        verbose_name = 'Compte tiers'
        verbose_name_plural = 'Comptes tiers'
        unique_together = ['tiers', 'exercice']
    
    def __str__(self):
        return f"{self.tiers.code} - {self.exercice.code}: {self.solde}"
    
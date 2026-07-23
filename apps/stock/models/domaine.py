# apps/stock/models/domaine.py
from django.db import models


class Domaine(models.Model):
    """Domaine d'utilisation d'un produit"""
    nom = models.CharField(max_length=100, unique=True)
    icone = models.CharField(max_length=50, blank=True, default='')
    actif = models.BooleanField(default=True)
    ordre = models.IntegerField(default=0)

    class Meta:
        db_table = 'stock_domaines'
        verbose_name = 'Domaine'
        verbose_name_plural = 'Domaines'
        ordering = ['ordre', 'nom']

    def __str__(self):
        return self.nom

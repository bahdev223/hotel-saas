# apps/stock/models/categorie.py
from django.db import models


class CategorieProduit(models.Model):
    """Catégorie de produit"""
    nom = models.CharField(max_length=100)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'stock_categories'
        verbose_name = 'Catégorie'
        verbose_name_plural = 'Catégories'
        ordering = ['nom']
    
    def __str__(self):
        return self.nom
    
    
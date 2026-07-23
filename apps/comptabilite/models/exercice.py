
from django.db import models
from decimal import Decimal
from datetime import date


class ExerciceModel(models.Model):
    """Exercice comptable"""
    code = models.CharField(max_length=20, unique=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    cloture = models.BooleanField(default=False)
    date_cloture = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'compta_exercices'
        verbose_name = 'Exercice comptable'
        verbose_name_plural = 'Exercices comptables'
        ordering = ['-date_debut']
    
    def __str__(self):
        return f"Exercice {self.code} ({self.date_debut} - {self.date_fin})"
    
    @property
    def est_ouvert(self):
        return not self.cloture


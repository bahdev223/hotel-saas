
from django.db import models
from decimal import Decimal
from datetime import date


class JournalModel(models.Model):
    """Journal comptable"""
    
    TYPE_CHOICES = [
        ('ACHATS', 'Achats'),
        ('VENTES', 'Ventes'),
        ('BANQUE', 'Banque'),
        ('CAISSE', 'Caisse'),
        ('OD', 'Opérations Diverses'),
    ]
    
    code = models.CharField(max_length=10, unique=True)
    libelle = models.CharField(max_length=100)
    type_journal = models.CharField(max_length=20, choices=TYPE_CHOICES)
    actif = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'compta_journaux'
        verbose_name = 'Journal'
        verbose_name_plural = 'Journaux'
    
    def __str__(self):
        return f"{self.code} - {self.libelle}"


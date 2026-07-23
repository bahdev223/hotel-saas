# apps/comptabilite/models/ecriture.py
from django.db import models
from decimal import Decimal
from datetime import date

# ⚠️ Ne pas importer directement, utiliser des strings
# from apps.comptabilite.models import CompteModel, TiersModel
# from .journal import JournalModel
# from .exercice import ExerciceModel


class EcritureModel(models.Model):
    """Écriture comptable"""
    
    reference = models.CharField(max_length=50, unique=True)
    date_ecriture = models.DateField()
    libelle = models.TextField()
    journal = models.ForeignKey('JournalModel', on_delete=models.CASCADE)
    piece = models.CharField(max_length=50, blank=True, null=True)
    exercice = models.ForeignKey('ExerciceModel', on_delete=models.CASCADE)
    validee = models.BooleanField(default=False)
    date_validation = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.CharField(max_length=100, blank=True, null=True)
    
    class Meta:
        db_table = 'compta_ecritures'
        verbose_name = 'Écriture comptable'
        verbose_name_plural = 'Écritures comptables'
        ordering = ['-date_ecriture', '-created_at']
    
    def __str__(self):
        return f"{self.reference} - {self.date_ecriture} - {self.libelle[:50]}"
    
    @property
    def total_debit(self):
        return sum(l.debit for l in self.lignes.all())
    
    @property
    def total_credit(self):
        return sum(l.credit for l in self.lignes.all())
    
    @property
    def est_equilibree(self):
        return self.total_debit == self.total_credit


class LigneEcritureModel(models.Model):
    """Ligne d'écriture comptable"""
    
    ecriture = models.ForeignKey(EcritureModel, on_delete=models.CASCADE, related_name='lignes')
    compte = models.ForeignKey('CompteModel', on_delete=models.CASCADE)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    libelle = models.CharField(max_length=200, blank=True, null=True)
    tiers = models.ForeignKey('TiersModel', on_delete=models.CASCADE, null=True, blank=True)
    
    class Meta:
        db_table = 'compta_lignes_ecritures'
        verbose_name = 'Ligne d\'écriture'
        verbose_name_plural = 'Lignes d\'écritures'
    
    def __str__(self):
        return f"{self.ecriture.reference} - {self.compte.code} - {self.debit or self.credit}"
    
    def clean(self):
        from django.core.exceptions import ValidationError
        if self.debit and self.credit:
            raise ValidationError("Une ligne ne peut pas avoir à la fois débit et crédit")
        if self.debit < 0 or self.credit < 0:
            raise ValidationError("Les montants doivent être positifs")

from django.db import models
from decimal import Decimal
from datetime import date


class CompteModel(models.Model):
    """Plan comptable SYSCOHADA"""
    
    NATURE_CHOICES = [
        ('ACTIF', 'Actif'),
        ('PASSIF', 'Passif'),
        ('CHARGE', 'Charge'),
        ('PRODUIT', 'Produit'),
        ('MIXTE', 'Mixte'),
        ('NEUTRE', 'Neutre'),
    ]
    
    SENS_CHOICES = [
        ('DEBIT', 'Débit'),
        ('CREDIT', 'Crédit'),
        ('MIXTE', 'Mixte'),
    ]
    
    TYPE_CHOICES = [
        ('classe', 'Classe'),
        ('groupe', 'Groupe'),
        ('compte', 'Compte'),
        ('sous_compte', 'Sous-compte'),
    ]
    
    CATEGORIE_CHOICES = [
        ('bilan', 'Bilan'),
        ('resultat', 'Résultat'),
        ('hors_bilan', 'Hors bilan'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=100)
    nature = models.CharField(max_length=10, choices=NATURE_CHOICES)
    sens = models.CharField(max_length=10, choices=SENS_CHOICES)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='enfants')
    niveau = models.IntegerField(default=1)
    type_compte = models.CharField(max_length=20, choices=TYPE_CHOICES, default='compte')
    est_mouvement = models.BooleanField(default=True)
    categorie = models.CharField(max_length=20, choices=CATEGORIE_CHOICES, default='bilan')
    actif = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'compta_comptes'
        verbose_name = 'Compte comptable'
        verbose_name_plural = 'Comptes comptables'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.libelle}"
    
    @property
    def classe(self):
        return self.code[0] if self.code else ""
    
    @property
    def est_lettrable(self):
        comptes_lettrables = ["40", "41", "42", "43", "44", "45"]
        return any(self.code.startswith(c) for c in comptes_lettrables)
    
    @property
    def est_tva(self):
        comptes_tva = ["443", "444", "445"]
        return any(self.code.startswith(c) for c in comptes_tva)
    
    def get_solde_normal(self):
        if self.nature in ["ACTIF", "CHARGE"]:
            return "DEBIT"
        elif self.nature in ["PASSIF", "PRODUIT"]:
            return "CREDIT"
        return "MIXTE"

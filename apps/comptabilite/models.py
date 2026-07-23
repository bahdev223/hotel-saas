# apps/comptabilite/models.py
"""
Modèles Django pour la comptabilité
Correspondent aux modèles de comptabilite_sahel
"""

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


class TiersModel(models.Model):
    """Tiers (clients, fournisseurs, etc.)"""
    
    TYPE_CHOICES = [
        ('CLIENT', 'Client'),
        ('FOURNISSEUR', 'Fournisseur'),
        ('PERSONNEL', 'Personnel'),
        ('ETAT', 'État'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    type_tiers = models.CharField(max_length=20, choices=TYPE_CHOICES)
    compte = models.ForeignKey(CompteModel, on_delete=models.CASCADE, related_name='tiers')
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    identifiant_fiscal = models.CharField(max_length=50, blank=True, null=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'compta_tiers'
        verbose_name = 'Tiers'
        verbose_name_plural = 'Tiers'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    @property
    def est_client(self):
        return self.type_tiers == "CLIENT"
    
    @property
    def est_fournisseur(self):
        return self.type_tiers == "FOURNISSEUR"


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


class EcritureModel(models.Model):
    """Écriture comptable"""
    
    reference = models.CharField(max_length=50, unique=True)
    date_ecriture = models.DateField()
    libelle = models.TextField()
    journal = models.ForeignKey(JournalModel, on_delete=models.CASCADE)
    piece = models.CharField(max_length=50, blank=True, null=True)
    exercice = models.ForeignKey(ExerciceModel, on_delete=models.CASCADE)
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
    compte = models.ForeignKey(CompteModel, on_delete=models.CASCADE)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    libelle = models.CharField(max_length=200, blank=True, null=True)
    tiers = models.ForeignKey(TiersModel, on_delete=models.CASCADE, null=True, blank=True)
    
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


class CompteTiersModel(models.Model):
    """Solde des comptes de tiers"""
    
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
    
    
    
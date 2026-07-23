# apps/comptabilite/models/rapprochement.py
from django.db import models
from django.contrib.auth.models import User
from apps.tresorerie.models import Caisse


class ReleveBancaire(models.Model):
    """Relevé bancaire importé"""
    
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='releves')
    date_debut = models.DateField()
    date_fin = models.DateField()
    solde_ouverture = models.DecimalField(max_digits=12, decimal_places=2)
    solde_cloture = models.DecimalField(max_digits=12, decimal_places=2)
    fichier = models.FileField(upload_to='releves_bancaires/', blank=True, null=True)
    statut = models.CharField(max_length=20, default='BROUILLON', choices=[
        ('BROUILLON', 'Brouillon'),
        ('EN_COURS', 'En cours'),
        ('RAPPROCHE', 'Rapproché'),
        ('CLOTURE', 'Clôturé'),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    class Meta:
        db_table = 'compta_releves_bancaires'
        ordering = ['-date_fin']
    
    def __str__(self):
        return f"Relevé {self.caisse.nom} - {self.date_debut} au {self.date_fin}"
    
    @property
    def total_credit(self):
        return self.lignes.filter(sens='CREDIT').aggregate(total=models.Sum('montant'))['total'] or 0
    
    @property
    def total_debit(self):
        return self.lignes.filter(sens='DEBIT').aggregate(total=models.Sum('montant'))['total'] or 0


class LigneReleveBancaire(models.Model):
    """Ligne de relevé bancaire"""
    
    SENS_CHOICES = [
        ('CREDIT', 'Crédit (entrée)'),
        ('DEBIT', 'Débit (sortie)'),
    ]
    
    STATUT_CHOICES = [
        ('NON_RAPPROCHE', 'Non rapproché'),
        ('RAPPROCHE', 'Rapproché'),
        ('ECART', 'Écart'),
    ]
    
    releve = models.ForeignKey(ReleveBancaire, on_delete=models.CASCADE, related_name='lignes')
    date_operation = models.DateField()
    libelle = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    sens = models.CharField(max_length=10, choices=SENS_CHOICES)
    reference = models.CharField(max_length=100, blank=True, null=True)
    
    statut = models.CharField(max_length=20, default='NON_RAPPROCHE', choices=STATUT_CHOICES)
    ecriture_rapprochee = models.ForeignKey('EcritureModel', on_delete=models.SET_NULL, null=True, blank=True)
    ecart_justification = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'compta_lignes_releve'
        ordering = ['date_operation']
    
    def __str__(self):
        return f"{self.date_operation} - {self.libelle} - {self.montant}"


class EcartRapprochement(models.Model):
    """Écart de rapprochement bancaire"""
    
    releve = models.ForeignKey(ReleveBancaire, on_delete=models.CASCADE, related_name='ecarts')
    type_ecart = models.CharField(max_length=20, choices=[
        ('COMMISSION', 'Commission bancaire'),
        ('INTERET', 'Intérêts'),
        ('ERREUR', 'Erreur de saisie'),
        ('AUTRE', 'Autre'),
    ])
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    sens = models.CharField(max_length=10, choices=LigneReleveBancaire.SENS_CHOICES)
    justification = models.TextField()
    ecriture_correction = models.ForeignKey('EcritureModel', on_delete=models.SET_NULL, null=True, blank=True)
    valide = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'compta_ecarts_rapprochement'
        
        
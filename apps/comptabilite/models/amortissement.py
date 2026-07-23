# apps/comptabilite/models/amortissement.py
from django.db import models
from decimal import Decimal
from datetime import date

# ⚠️ Utiliser une string pour l'import différé (ForeignKey avec string)
# from apps.comptabilite.models import CompteModel  # ← SUPPRIMER


class Immobilisation(models.Model):
    """Immobilisation (actif fixe)"""
    
    TYPE_CHOICES = [
        ('CORPORELLE', 'Immobilisation corporelle'),
        ('INCORPORELLE', 'Immobilisation incorporelle'),
        ('FINANCIERE', 'Immobilisation financière'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=200)
    type_immobilisation = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date_acquisition = models.DateField()
    valeur_originale = models.DecimalField(max_digits=12, decimal_places=2)
    valeur_residuelle = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    duree_ans = models.IntegerField(help_text="Durée d'amortissement en années")
    
    # 🔥 Utiliser des strings pour les ForeignKey pour éviter l'import circulaire
    compte_immobilisation = models.ForeignKey(
        'CompteModel', 
        on_delete=models.PROTECT, 
        related_name='immobilisations'
    )
    compte_amortissement = models.ForeignKey(
        'CompteModel', 
        on_delete=models.PROTECT, 
        related_name='amortissements'
    )
    compte_charge = models.ForeignKey(
        'CompteModel', 
        on_delete=models.PROTECT, 
        related_name='charges_amortissement'
    )
    
    statut = models.CharField(max_length=20, default='ACTIF', choices=[('ACTIF', 'Actif'), ('CESSION', 'Cédé'), ('SORTIE', 'Sorti')])
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compta_immobilisations'
        verbose_name = 'Immobilisation'
        verbose_name_plural = 'Immobilisations'
    
    def __str__(self):
        return f"{self.code} - {self.libelle}"
    
    @property
    def base_amortissable(self):
        """Base amortissable = Valeur - Valeur résiduelle"""
        return self.valeur_originale - self.valeur_residuelle
    
    @property
    def amortissement_annuel(self):
        """Amortissement linéaire annuel"""
        if self.duree_ans > 0:
            return self.base_amortissable / self.duree_ans
        return Decimal('0')
    
    @property
    def amortissement_mensuel(self):
        """Amortissement linéaire mensuel"""
        return self.amortissement_annuel / 12
    
    def calculer_amortissements_cumules(self, date_fin=None):
        """Calcule les amortissements cumulés jusqu'à une date"""
        from datetime import datetime
        if date_fin is None:
            date_fin = date.today()
        
        mois = (date_fin.year - self.date_acquisition.year) * 12 + (date_fin.month - self.date_acquisition.month)
        if mois < 0:
            return Decimal('0')
        return self.amortissement_mensuel * mois
    
    def valeur_nette_comptable(self, date_fin=None):
        """Valeur nette comptable = Valeur originale - Amortissements cumulés"""
        if date_fin is None:
            date_fin = date.today()
        return self.valeur_originale - self.calculer_amortissements_cumules(date_fin)


class PlanAmortissement(models.Model):
    """Plan d'amortissement détaillé"""
    
    immobilisation = models.ForeignKey(Immobilisation, on_delete=models.CASCADE, related_name='plan_amortissement')
    periode = models.DateField()  # Mois/Année
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    amortissement_cumule = models.DecimalField(max_digits=12, decimal_places=2)
    valeur_nette = models.DecimalField(max_digits=12, decimal_places=2)
    ecriture_generee = models.BooleanField(default=False)
    ecriture_reference = models.CharField(max_length=50, blank=True, null=True)
    
    class Meta:
        db_table = 'compta_plans_amortissement'
        ordering = ['periode']
        unique_together = ['immobilisation', 'periode']
    
    def __str__(self):
        return f"{self.immobilisation.code} - {self.periode.strftime('%m/%Y')}"
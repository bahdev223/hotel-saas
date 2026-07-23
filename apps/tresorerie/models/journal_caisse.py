# apps/tresorerie/models/journal_caisse.py
from django.db import models
from .caisse import Caisse


class JournalCaisse(models.Model):
    """Journal de caisse (clôture journalière)"""
    
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='journaux')
    date_journal = models.DateField(auto_now_add=True)
    solde_ouverture = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_entrees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_sorties = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    solde_theorique = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    solde_reel = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ecart = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cloture = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'tresorerie_journaux'
        verbose_name = 'Journal de caisse'
        verbose_name_plural = 'Journaux de caisse'
        unique_together = ['caisse', 'date_journal']

    def __str__(self):
        return f"{self.caisse.nom} - {self.date_journal}"


class LigneJournalCaisse(models.Model):
    """Ligne détaillée du journal de caisse"""
    
    journal = models.ForeignKey(JournalCaisse, on_delete=models.CASCADE, related_name='lignes')
    type_operation = models.CharField(max_length=50)  # vente, achat, transfert, etc.
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    sens = models.CharField(max_length=10)  # ENTREE / SORTIE
    reference = models.CharField(max_length=100, blank=True, null=True)
    libelle = models.CharField(max_length=255)

    class Meta:
        db_table = 'tresorerie_journal_lignes'

    def __str__(self):
        return f"{self.journal.caisse.nom} - {self.sens} - {self.montant:,.0f} F"
    
    
    
# apps/tresorerie/models/transfert.py
from django.db import models
from django.contrib.auth.models import User
from .caisse import Caisse


class TransfertCaisse(models.Model):
    source = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='transferts_sortants')
    destination = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='transferts_entrants')
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    reference = models.CharField(max_length=100, unique=True)
    date = models.DateTimeField(auto_now_add=True)
    valide_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'tresorerie_transferts'
        verbose_name = 'Transfert'
        verbose_name_plural = 'Transferts'

    def __str__(self):
        return f"Transfert {self.source.code} → {self.destination.code} : {self.montant:,.0f} F"
    
    
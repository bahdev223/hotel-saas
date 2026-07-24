from django.db import models
from django.conf import settings
from ..constants import StatutShift


class ShiftEmploye(models.Model):
    affectation = models.ForeignKey(
        'AffectationPointVente', on_delete=models.PROTECT, related_name='shifts',
    )
    debut_prevu = models.DateTimeField()
    fin_prevue = models.DateTimeField()
    debut_reel = models.DateTimeField(null=True, blank=True)
    fin_reelle = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=StatutShift.choices, default=StatutShift.PLANIFIE)
    notes = models.TextField(blank=True)
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    annule_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name='+')
    motif_annulation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Shift employé"
        verbose_name_plural = "Shifts employés"
        ordering = ['-debut_prevu']

    def __str__(self):
        return f"{self.affectation.employe} @ {self.affectation.point_vente.nom} ({self.debut_prevu.date()})"

    @property
    def employe(self):
        return self.affectation.employe

    @property
    def point_vente(self):
        return self.affectation.point_vente

    @property
    def role(self):
        return self.affectation.role

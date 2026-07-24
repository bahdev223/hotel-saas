from django.db import models
from apps.rh.models import Employe
from ..constants import RolePOS


class AffectationPointVente(models.Model):
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='affectations_points_vente')
    point_vente = models.ForeignKey('PointVente', on_delete=models.CASCADE, related_name='affectations_employes')
    role = models.CharField(max_length=30, choices=RolePOS.choices, default=RolePOS.CAISSIER)

    peut_vendre = models.BooleanField(default=False)
    peut_encaisser = models.BooleanField(default=False)
    peut_ouvrir_caisse = models.BooleanField(default=False)
    peut_fermer_caisse = models.BooleanField(default=False)
    peut_annuler_vente = models.BooleanField(default=False)
    peut_accorder_remise = models.BooleanField(default=False)
    peut_consulter_rapports = models.BooleanField(default=False)

    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    principal = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Affectation point de vente"
        verbose_name_plural = "Affectations points de vente"
        unique_together = ['employe', 'point_vente', 'role']

    def __str__(self):
        return f"{self.employe} → {self.point_vente.nom} ({self.get_role_display()})"

from django.db import models
from apps.tresorerie.models import Caisse


class CaissePointVente(models.Model):
    point_vente = models.ForeignKey('PointVente', on_delete=models.CASCADE, related_name='caisses_affectees')
    caisse = models.OneToOneField(Caisse, on_delete=models.PROTECT, related_name='affectation_pos')
    principale = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Caisse de point de vente"
        verbose_name_plural = "Caisses de points de vente"
        unique_together = ['point_vente', 'caisse']

    def __str__(self):
        return f"{self.point_vente.nom} → {self.caisse.nom}"

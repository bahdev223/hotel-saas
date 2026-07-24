from django.db import models
from apps.stock.models import Entrepot
from ..constants import TypePointVente, ModePrelevement


class PointVenteEntrepot(models.Model):
    point_vente = models.ForeignKey('PointVente', on_delete=models.CASCADE, related_name='entrepots_autorises')
    entrepot = models.ForeignKey(Entrepot, on_delete=models.CASCADE, related_name='points_vente_autorises')
    priorite = models.PositiveSmallIntegerField(default=1)
    principal = models.BooleanField(default=False)
    autorise_vente = models.BooleanField(default=True)
    autorise_retour = models.BooleanField(default=True)
    actif = models.BooleanField(default=True)

    class Meta:
        db_table = 'pos_point_vente_entrepots'
        unique_together = ('point_vente', 'entrepot')
        verbose_name = "Liaison point de vente \u2194 entrep\u00f4t"
        verbose_name_plural = "Liaisons points de vente \u2194 entrep\u00f4ts"

    def __str__(self):
        return f"{self.point_vente.nom} \u2192 {self.entrepot.nom}"


class PointVente(models.Model):
    code = models.CharField(max_length=30, unique=True)
    nom = models.CharField(max_length=120)
    type = models.CharField(max_length=30, choices=TypePointVente.choices, default=TypePointVente.AUTRE)
    description = models.TextField(blank=True)
    actif = models.BooleanField(default=True)
    imprimante_nom = models.CharField(max_length=100, blank=True)
    impression_auto = models.BooleanField(default=True)
    exiger_planning_pour_acces = models.BooleanField(default=True)
    exiger_planning_pour_caisse = models.BooleanField(default=True)
    mode_prelevement_stock = models.CharField(
        max_length=20, choices=ModePrelevement.choices, default=ModePrelevement.STRICT,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pos_points_vente'
        verbose_name = 'Point de vente'
        verbose_name_plural = 'Points de vente'

    def __str__(self):
        return f"{self.nom} ({self.get_type_display()})"

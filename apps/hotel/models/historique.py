from django.db import models
from django.conf import settings


class HistoriqueStatutChambre(models.Model):
    chambre = models.ForeignKey(
        "hotel.UniteModel",
        on_delete=models.CASCADE,
        related_name="historique_statuts",
    )
    ancien_statut = models.CharField(max_length=20)
    nouveau_statut = models.CharField(max_length=20)
    modifie_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    motif = models.TextField(blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Historique de statut"
        verbose_name_plural = "Historiques des statuts"
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.chambre} : {self.ancien_statut} -> {self.nouveau_statut}"

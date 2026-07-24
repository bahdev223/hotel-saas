from django.db import models


class Occupant(models.Model):
    sejour = models.ForeignKey(
        "hotel.Sejour",
        on_delete=models.CASCADE,
        related_name="occupants",
    )
    nom_complet = models.CharField(max_length=200)
    type_piece = models.CharField(max_length=50, blank=True)
    numero_piece = models.CharField(max_length=50, blank=True)
    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    est_principal = models.BooleanField(default=False)
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Occupant"
        verbose_name_plural = "Occupants"

    def __str__(self):
        return self.nom_complet

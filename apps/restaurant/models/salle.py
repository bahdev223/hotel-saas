from django.db import models
from django.core.exceptions import ValidationError


class SalleModel(models.Model):
    """Zone physique de service d'un point de vente Restaurant."""

    point_vente = models.ForeignKey(
        "pos.PointVente",
        on_delete=models.PROTECT,
        related_name="salles_restaurant",
    )
    code = models.CharField(max_length=30)
    nom = models.CharField(max_length=100)
    ordre = models.PositiveSmallIntegerField(default=0)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "restaurant_salles"
        verbose_name = "Salle"
        verbose_name_plural = "Salles"
        ordering = ["ordre", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["point_vente", "code"],
                name="unique_salle_code_par_restaurant",
            ),
        ]

    def clean(self):
        super().clean()
        if self.point_vente_id and self.point_vente.type != "RESTAURATION":
            raise ValidationError(
                "Une salle doit appartenir à un point de vente Restaurant."
            )

    def __str__(self):
        return f"{self.nom} · {self.point_vente.nom}"

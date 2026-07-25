from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal

class Tarif(models.Model):
    unite = models.ForeignKey(
        "hotel.UniteModel",
        on_delete=models.CASCADE,
        related_name="tarifs"
    )
    nom = models.CharField(
        max_length=100, 
        help_text="Ex: Nuitée, Sieste, Mensuel"
    )
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["montant"]
        verbose_name = "Tarif"
        verbose_name_plural = "Tarifs"

    def __str__(self):
        return f"{self.nom} - {self.montant} F"

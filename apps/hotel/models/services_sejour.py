from django.db import models


class ServiceSejour(models.Model):
    sejour = models.ForeignKey(
        "hotel.Sejour",
        on_delete=models.CASCADE,
        related_name="services",
    )
    nom = models.CharField(max_length=200)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    quantite = models.PositiveIntegerField(default=1)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)
    facture = models.ForeignKey(
        "facturation.FactureModel",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="services_sejour",
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Service du séjour"
        verbose_name_plural = "Services du séjour"
        ordering = ["-cree_le"]

    def __str__(self):
        return f"{self.nom} - {self.montant_total}"

from django.db import models


class Lot(models.Model):
    numero_lot = models.CharField(max_length=100, unique=True, verbose_name="NÂ° de lot")
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="lots",
        verbose_name="Article",
    )
    date_fabrication = models.DateField(null=True, blank=True, verbose_name="Date de fabrication")
    date_peremption = models.DateField(null=True, blank=True, verbose_name="Date de pÃ©remption")
    prix_revient_unitaire = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        verbose_name="Prix de revient unitaire",
    )
    quantite_initiale = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="QuantitÃ© initiale",
    )
    quantite_restante = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="QuantitÃ© restante",
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="CrÃ©Ã© le")

    class Meta:
        verbose_name = "Lot"
        verbose_name_plural = "Lots"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["article", "date_peremption"]),
        ]

    def __str__(self):
        return f"Lot {self.numero_lot} â€” {self.article.code}"


class NumeroSerie(models.Model):
    numero = models.CharField(max_length=100, unique=True, verbose_name="NÂ° de sÃ©rie")
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="numeros_serie",
        verbose_name="Article",
    )
    lot = models.ForeignKey(
        Lot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="numeros_serie",
        verbose_name="Lot",
    )
    depot_actuel = models.ForeignKey(
        "Depot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="numeros_serie",
        verbose_name="DÃ©pÃ´t actuel",
    )
    est_disponible = models.BooleanField(default=True, verbose_name="Disponible")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="CrÃ©Ã© le")

    class Meta:
        verbose_name = "NumÃ©ro de sÃ©rie"
        verbose_name_plural = "NumÃ©ros de sÃ©rie"
        ordering = ["numero"]

    def __str__(self):
        return self.numero

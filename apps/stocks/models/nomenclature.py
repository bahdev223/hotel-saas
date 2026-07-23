from django.db import models


class Nomenclature(models.Model):
    code = models.CharField(max_length=100, unique=True, verbose_name="Code nomenclature")
    libelle = models.CharField(max_length=500, verbose_name="LibellÃ©")
    article_compose = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="nomenclatures_compose",
        verbose_name="Article composÃ©",
    )
    quantite_produite = models.DecimalField(
        max_digits=18, decimal_places=6, default=1,
        verbose_name="QuantitÃ© produite",
    )
    actif = models.BooleanField(default=True, verbose_name="Actif")
    description = models.TextField(blank=True, verbose_name="Description")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="CrÃ©Ã© le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mis Ã  jour le")

    class Meta:
        verbose_name = "Nomenclature"
        verbose_name_plural = "Nomenclatures"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} â€” {self.article_compose.designation}"


class ComposantNomenclature(models.Model):
    nomenclature = models.ForeignKey(
        Nomenclature,
        on_delete=models.CASCADE,
        related_name="composants",
        verbose_name="Nomenclature",
    )
    article = models.ForeignKey(
        "Article",
        on_delete=models.PROTECT,
        related_name="nomenclatures_composant",
        verbose_name="Article composant",
    )
    quantite = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="QuantitÃ©",
    )
    perte = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        verbose_name="Taux de perte (%)",
    )

    class Meta:
        verbose_name = "Composant de nomenclature"
        verbose_name_plural = "Composants de nomenclature"
        ordering = ["nomenclature", "article"]

    def __str__(self):
        return f"{self.nomenclature.code} â†’ {self.article.code} x{self.quantite}"

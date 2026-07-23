from django.db import models
from django.core.validators import MinValueValidator


class ConditionnementArticle(models.Model):
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="conditionnements",
        verbose_name="Article",
    )
    nom = models.CharField(max_length=100, verbose_name="Nom du conditionnement")
    unite = models.ForeignKey(
        "Unite",
        on_delete=models.PROTECT,
        verbose_name="Unité",
    )
    facteur_conversion = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        validators=[MinValueValidator(0)],
        verbose_name="Facteur de conversion",
        help_text="Nombre d'unités de base dans ce conditionnement",
    )
    achat = models.BooleanField(default=True, verbose_name="Conditionnement d'achat")
    vente = models.BooleanField(default=False, verbose_name="Conditionnement de vente")
    stock = models.BooleanField(default=False, verbose_name="Conditionnement de stock")
    ordre = models.PositiveIntegerField(default=0, verbose_name="Ordre d'affichage")

    class Meta:
        verbose_name = "Conditionnement d'article"
        verbose_name_plural = "Conditionnements d'article"
        ordering = ["article", "ordre"]
        unique_together = [["article", "nom"]]

    def __str__(self):
        return f"{self.nom} ({self.facteur_conversion} x {self.unite.code})"

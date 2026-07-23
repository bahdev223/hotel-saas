from django.db import models
from apps.stocks.constants import StatutInventaire


class Inventaire(models.Model):
    reference = models.CharField(max_length=100, unique=True, verbose_name="RÃ©fÃ©rence")
    depot = models.ForeignKey(
        "Depot",
        on_delete=models.PROTECT,
        related_name="inventaires",
        verbose_name="DÃ©pÃ´t",
    )
    date_inventaire = models.DateField(verbose_name="Date d'inventaire")
    statut = models.CharField(
        max_length=20,
        choices=StatutInventaire.choices,
        default=StatutInventaire.BROUILLON,
        verbose_name="Statut",
    )
    realise_par = models.CharField(
        max_length=255, blank=True, verbose_name="RÃ©alisÃ© par",
    )
    notes = models.TextField(blank=True, verbose_name="Notes")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="CrÃ©Ã© le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mis Ã  jour le")

    class Meta:
        verbose_name = "Inventaire"
        verbose_name_plural = "Inventaires"
        ordering = ["-date_inventaire"]

    def __str__(self):
        return f"INV {self.reference} â€” {self.depot.code} ({self.date_inventaire})"


class LigneInventaire(models.Model):
    inventaire = models.ForeignKey(
        Inventaire,
        on_delete=models.CASCADE,
        related_name="lignes",
        verbose_name="Inventaire",
    )
    article = models.ForeignKey(
        "Article",
        on_delete=models.PROTECT,
        related_name="lignes_inventaire",
        verbose_name="Article",
    )
    lot = models.ForeignKey(
        "Lot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lignes_inventaire",
        verbose_name="Lot",
    )
    quantite_theorique = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="QuantitÃ© thÃ©orique",
    )
    quantite_reelle = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="QuantitÃ© rÃ©elle",
    )

    class Meta:
        verbose_name = "Ligne d'inventaire"
        verbose_name_plural = "Lignes d'inventaire"
        unique_together = [["inventaire", "article", "lot"]]

    @property
    def ecart(self):
        return self.quantite_reelle - self.quantite_theorique

    def __str__(self):
        return f"{self.article.code}: thÃ©orique={self.quantite_theorique} / rÃ©el={self.quantite_reelle}"

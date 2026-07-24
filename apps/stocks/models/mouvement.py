from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from apps.stocks.constants import NatureMouvement


class MouvementStock(models.Model):
    reference = models.CharField(max_length=100, unique=True, verbose_name="RÃ©fÃ©rence")
    nature = models.CharField(
        max_length=20,
        choices=NatureMouvement.choices,
        verbose_name="Nature du mouvement",
    )
    article = models.ForeignKey(
        "Article",
        on_delete=models.PROTECT,
        related_name="mouvements",
        verbose_name="Article",
    )
    depot = models.ForeignKey(
        "Depot",
        on_delete=models.PROTECT,
        related_name="mouvements",
        verbose_name="DÃ©pÃ´t",
    )
    emplacement = models.ForeignKey(
        "Emplacement",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mouvements",
        verbose_name="Emplacement",
    )
    lot = models.ForeignKey(
        "Lot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="mouvements",
        verbose_name="Lot",
    )
    source_operation = models.ForeignKey(
        "SourceOperation",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="mouvements",
        verbose_name="OpÃ©ration source",
    )
    reference_externe = models.CharField(
        max_length=255, blank=True, verbose_name="RÃ©f. externe",
        help_text="RÃ©fÃ©rence libre du document mÃ©tier (ex: FAC-2026-001254)",
    )
    quantite = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="QuantitÃ©",
    )
    prix_unitaire = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        verbose_name="Prix unitaire",
    )
    cout_total = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        verbose_name="CoÃ»t total",
    )
    date_mouvement = models.DateTimeField(verbose_name="Date du mouvement")
    libelle = models.CharField(max_length=500, blank=True, verbose_name="LibellÃ©")
    valide = models.BooleanField(default=False, verbose_name="ValidÃ©")

    source_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Type de source",
    )
    source_object_id = models.PositiveIntegerField(
        null=True, blank=True, verbose_name="ID source",
    )
    source = GenericForeignKey("source_content_type", "source_object_id")

    created_by = models.CharField(
        max_length=255, blank=True, verbose_name="CrÃ©Ã© par",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="CrÃ©Ã© le")

    class Meta:
        verbose_name = "Mouvement de stock"
        verbose_name_plural = "Mouvements de stock"
        ordering = ["-date_mouvement"]
        indexes = [
            models.Index(fields=["article", "depot"]),
            models.Index(fields=["nature"]),
            models.Index(fields=["date_mouvement"]),
            models.Index(fields=["valide"]),
            models.Index(fields=["source_content_type", "source_object_id"]),
        ]

    def __str__(self):
        src = f" [{self.source_operation.code}]" if self.source_operation else ""
        return f"{self.reference} â€” {self.nature} {self.quantite} x {self.article.code}{src}"

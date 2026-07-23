from django.db import models
from apps.stocks.constants import SOURCES_SYSTEME, FamilleSource


class SourceOperation(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    nom = models.CharField(max_length=255, verbose_name="Nom")
    famille = models.CharField(
        max_length=30,
        choices=FamilleSource.choices,
        default=FamilleSource.AUTRE,
        verbose_name="Famille",
    )
    active = models.BooleanField(default=True, verbose_name="Active")
    systeme = models.BooleanField(default=False, verbose_name="SystÃ¨me")

    class Meta:
        verbose_name = "OpÃ©ration source"
        verbose_name_plural = "OpÃ©rations source"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["famille"]),
        ]

    def __str__(self):
        return f"{self.code} â€” {self.nom}"

    @classmethod
    def seed(cls):
        for code, data in SOURCES_SYSTEME.items():
            cls.objects.get_or_create(
                code=code,
                defaults={
                    "nom": data["nom"],
                    "famille": data["famille"],
                    "systeme": True,
                },
            )

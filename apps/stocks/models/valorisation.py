from django.db import models


class Valorisation(models.Model):
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="valorisations",
        verbose_name="Article",
    )
    depot = models.ForeignKey(
        "Depot",
        on_delete=models.CASCADE,
        related_name="valorisations",
        verbose_name="DÃ©pÃ´t",
    )
    methode = models.CharField(
        max_length=10,
        choices=[
            ("PMP", "Prix Moyen PondÃ©rÃ©"),
            ("FIFO", "Premier entrÃ©, premier sorti"),
            ("STANDARD", "CoÃ»t standard"),
            ("NONE", "Aucune"),
        ],
        default="PMP",
        verbose_name="MÃ©thode",
    )
    cout_unitaire_moyen = models.DecimalField(
        max_digits=18, decimal_places=6, default=0,
        verbose_name="CoÃ»t unitaire moyen",
    )
    quantite_totale = models.DecimalField(
        max_digits=18, decimal_places=6, default=0,
        verbose_name="QuantitÃ© totale",
    )
    valeur_totale = models.DecimalField(
        max_digits=18, decimal_places=6, default=0,
        verbose_name="Valeur totale",
    )
    derniere_mise_a_jour = models.DateTimeField(
        auto_now=True, verbose_name="DerniÃ¨re mise Ã  jour",
    )

    class Meta:
        verbose_name = "Valorisation"
        verbose_name_plural = "Valorisations"
        unique_together = [["article", "depot"]]

    def __str__(self):
        return f"{self.article.code} @ {self.depot.code} â€” {self.methode}"


class CoucheValorisation(models.Model):
    """Couche FIFO â€” chaque entrÃ©e en stock crÃ©e une couche avec son prix."""
    article = models.ForeignKey(
        "Article",
        on_delete=models.CASCADE,
        related_name="couches_valorisation",
        verbose_name="Article",
    )
    depot = models.ForeignKey(
        "Depot",
        on_delete=models.CASCADE,
        related_name="couches_valorisation",
        verbose_name="DÃ©pÃ´t",
    )
    quantite_restante = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="QuantitÃ© restante",
    )
    prix_unitaire = models.DecimalField(
        max_digits=18, decimal_places=6, verbose_name="Prix unitaire",
    )
    date_entree = models.DateTimeField(verbose_name="Date d'entrÃ©e")
    mouvement = models.ForeignKey(
        "MouvementStock",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="couches_valorisation",
        verbose_name="Mouvement d'origine",
    )
    lot = models.ForeignKey(
        "Lot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="couches_valorisation",
        verbose_name="Lot",
    )

    class Meta:
        verbose_name = "Couche de valorisation"
        verbose_name_plural = "Couches de valorisation"
        ordering = ["date_entree", "id"]
        indexes = [
            models.Index(fields=["article", "depot", "date_entree"]),
        ]

    def __str__(self):
        return f"{self.article.code} @ {self.depot.code} â€” {self.quantite_restante} x {self.prix_unitaire}"

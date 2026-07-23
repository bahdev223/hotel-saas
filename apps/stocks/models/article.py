from django.db import models
from apps.stocks.constants import TypesArticle, CategorieUnite, COMPORTEMENT_PAR_DEFAUT


class TypeArticle(models.Model):
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    libelle = models.CharField(max_length=255, verbose_name="LibellÃ©")
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "Type d'article"
        verbose_name_plural = "Types d'article"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} â€” {self.libelle}"


class CategorieArticle(models.Model):
    nom = models.CharField(max_length=255, verbose_name="Nom")
    code = models.CharField(max_length=50, unique=True, verbose_name="Code")
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="enfants",
        verbose_name="CatÃ©gorie parente",
    )
    description = models.TextField(blank=True, verbose_name="Description")

    class Meta:
        verbose_name = "CatÃ©gorie d'article"
        verbose_name_plural = "CatÃ©gories d'article"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} â€” {self.nom}"


class Unite(models.Model):
    code = models.CharField(max_length=10, unique=True, verbose_name="Code")
    libelle = models.CharField(max_length=100, verbose_name="LibellÃ©")
    categorie = models.CharField(
        max_length=20,
        choices=CategorieUnite.choices,
        default=CategorieUnite.AUTRE,
        verbose_name="CatÃ©gorie d'unitÃ©",
    )

    class Meta:
        verbose_name = "UnitÃ©"
        verbose_name_plural = "UnitÃ©s"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} ({self.libelle})"


class ComportementArticle(models.Model):
    stockable = models.BooleanField(default=True, verbose_name="Stockable")
    vendable = models.BooleanField(default=True, verbose_name="Vendable")
    achetable = models.BooleanField(default=True, verbose_name="Achetable")
    perissable = models.BooleanField(default=False, verbose_name="PÃ©rissable")
    lot_obligatoire = models.BooleanField(default=False, verbose_name="Lot obligatoire")
    numero_serie = models.BooleanField(default=False, verbose_name="NumÃ©ro de sÃ©rie")
    inventoriable = models.BooleanField(default=True, verbose_name="Inventoriable")

    class Meta:
        verbose_name = "Comportement d'article"
        verbose_name_plural = "Comportements d'article"

    def __str__(self):
        traits = []
        if self.stockable:
            traits.append("Stockable")
        if self.vendable:
            traits.append("Vendable")
        if self.achetable:
            traits.append("Achetable")
        if self.perissable:
            traits.append("PÃ©rissable")
        if self.numero_serie:
            traits.append("NÂ° SÃ©rie")
        return " | ".join(traits) if traits else "Aucun comportement"

    @classmethod
    def creer_defaut(cls):
        return cls.objects.create(**COMPORTEMENT_PAR_DEFAUT)


class Article(models.Model):
    code = models.CharField(max_length=100, unique=True, verbose_name="Code article")
    designation = models.CharField(max_length=500, verbose_name="DÃ©signation")
    description = models.TextField(blank=True, verbose_name="Description")

    type_article = models.ForeignKey(
        TypeArticle,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="Type d'article",
    )
    categorie = models.ForeignKey(
        CategorieArticle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles",
        verbose_name="CatÃ©gorie",
    )
    unite_defaut = models.ForeignKey(
        Unite,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="UnitÃ© par dÃ©faut",
    )
    comportement = models.ForeignKey(
        ComportementArticle,
        on_delete=models.PROTECT,
        related_name="articles",
        verbose_name="Comportement",
    )
    methode_valorisation = models.CharField(
        max_length=10,
        choices=[
            ("PMP", "Prix Moyen PondÃ©rÃ©"),
            ("FIFO", "Premier entrÃ©, premier sorti"),
            ("DMP", "Dernier prix d'achat"),
            ("NONE", "Aucune"),
        ],
        default="PMP",
        verbose_name="MÃ©thode de valorisation",
    )

    seuil_alerte = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        verbose_name="Seuil d'alerte",
    )
    stock_min = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        verbose_name="Stock minimum",
    )
    stock_max = models.DecimalField(
        max_digits=18, decimal_places=6, null=True, blank=True,
        verbose_name="Stock maximum",
    )

    actif = models.BooleanField(default=True, verbose_name="Actif")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="CrÃ©Ã© le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mis Ã  jour le")

    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"
        ordering = ["code"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["type_article"]),
            models.Index(fields=["actif"]),
        ]

    def __str__(self):
        return f"[{self.code}] {self.designation}"

    @property
    def est_stockable(self):
        return self.comportement.stockable

    @property
    def est_vendable(self):
        return self.comportement.vendable

    @property
    def est_achetable(self):
        return self.comportement.achetable

    @property
    def est_perissable(self):
        return self.comportement.perissable

    @property
    def necessite_lot(self):
        return self.comportement.lot_obligatoire

    @property
    def est_serialise(self):
        return self.comportement.numero_serie

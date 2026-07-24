from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class TypeTarif(models.Model):
    class UniteFacturation(models.TextChoices):
        HEURE = "HEURE", "Heure"
        DEMI_JOURNEE = "DEMI_JOURNEE", "Demi-journée"
        JOURNEE = "JOURNEE", "Journée"
        NUITEE = "NUITEE", "Nuitée"
        SEMAINE = "SEMAINE", "Semaine"
        MOIS = "MOIS", "Mois"
        FORFAIT = "FORFAIT", "Forfait"

    code = models.SlugField(max_length=50, unique=True)
    nom = models.CharField(max_length=100)
    unite_facturation = models.CharField(
        max_length=30,
        choices=UniteFacturation.choices,
    )
    duree_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Durée de référence en minutes (ex: 60 pour heure, 1440 pour journée)",
    )
    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["ordre", "nom"]
        verbose_name = "Type de tarif"
        verbose_name_plural = "Types de tarifs"

    def __str__(self):
        return self.nom


class PlanTarifaire(models.Model):
    class TypeClient(models.TextChoices):
        TOUS = "TOUS", "Tous les clients"
        PARTICULIER = "PARTICULIER", "Particulier"
        ENTREPRISE = "ENTREPRISE", "Entreprise"
        AGENCE = "AGENCE", "Agence"
        ADMINISTRATION = "ADMINISTRATION", "Administration"

    etablissement = models.ForeignKey(
        "entreprises.Etablissement",
        on_delete=models.PROTECT,
        related_name="plans_tarifaires",
    )
    code = models.SlugField(max_length=50)
    nom = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    type_client = models.CharField(
        max_length=30,
        choices=TypeClient.choices,
        default=TypeClient.TOUS,
    )
    remboursable = models.BooleanField(default=True)
    petit_dejeuner_inclus = models.BooleanField(default=False)
    taxes_incluses = models.BooleanField(default=True)
    actif = models.BooleanField(default=True)
    priorite = models.PositiveSmallIntegerField(default=100)
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priorite", "nom"]
        constraints = [
            models.UniqueConstraint(
                fields=["etablissement", "code"],
                name="unique_plan_tarifaire_etablissement",
            )
        ]
        verbose_name = "Plan tarifaire"
        verbose_name_plural = "Plans tarifaires"

    def __str__(self):
        return self.nom


class TarifChambre(models.Model):
    etablissement = models.ForeignKey(
        "entreprises.Etablissement",
        on_delete=models.PROTECT,
        related_name="tarifs_chambres",
    )
    type_chambre = models.ForeignKey(
        "hotel.TypeChambre",
        on_delete=models.PROTECT,
        related_name="tarifs",
    )
    plan_tarifaire = models.ForeignKey(
        PlanTarifaire,
        on_delete=models.PROTECT,
        related_name="tarifs",
    )
    type_tarif = models.ForeignKey(
        TypeTarif,
        on_delete=models.PROTECT,
        related_name="tarifs_chambres",
    )
    montant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    nombre_personnes_incluses = models.PositiveSmallIntegerField(default=1)
    supplement_adulte = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    supplement_enfant = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    heure_debut = models.TimeField(null=True, blank=True)
    heure_fin = models.TimeField(null=True, blank=True)
    jours_semaine = models.JSONField(
        default=list,
        blank=True,
        help_text="Exemple : [0, 1, 2, 3, 4] pour lundi à vendredi.",
    )
    quantite_minimale = models.PositiveIntegerField(default=1)
    quantite_maximale = models.PositiveIntegerField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["type_chambre", "plan_tarifaire", "type_tarif", "montant"]
        verbose_name = "Tarif de chambre"
        verbose_name_plural = "Tarifs des chambres"

    def __str__(self):
        return f"{self.type_chambre} - {self.plan_tarifaire} - {self.type_tarif} : {self.montant}"


class CreneauTarifaire(models.Model):
    type_tarif = models.ForeignKey(
        TypeTarif,
        on_delete=models.CASCADE,
        related_name="creneaux",
    )
    nom = models.CharField(max_length=100)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Créneau tarifaire"
        verbose_name_plural = "Créneaux tarifaires"

    def __str__(self):
        return f"{self.nom} ({self.heure_debut} - {self.heure_fin})"

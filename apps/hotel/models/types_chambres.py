from django.db import models


class TypeChambre(models.Model):
    class Categorie(models.TextChoices):
        CHAMBRE = "CHAMBRE", "Chambre"
        VIP = "VIP", "VIP"
        SALLE = "SALLE", "Salle"
        ESPACE = "ESPACE", "Espace"
        ESPACE_BAR = "ESPACE_BAR", "Espace + Bar"
        BAR = "BAR", "Bar VIP"
        SUITE = "SUITE", "Suite"
        STUDIO = "STUDIO", "Studio"
        APPARTEMENT = "APPARTEMENT", "Appartement"
        DORTOIR = "DORTOIR", "Dortoir"

    etablissement = models.ForeignKey(
        "entreprises.Etablissement",
        on_delete=models.PROTECT,
        related_name="types_chambres",
        null=True,
        blank=True,
    )

    code = models.SlugField(max_length=50, unique=True)
    nom = models.CharField(max_length=100)
    categorie = models.CharField(
        max_length=30,
        choices=Categorie.choices,
        default=Categorie.CHAMBRE,
    )

    description = models.TextField(blank=True)
    capacite_par_defaut = models.PositiveSmallIntegerField(default=1)
    surface_par_defaut_m2 = models.FloatField(null=True, blank=True)

    couleur = models.CharField(max_length=20, blank=True, help_text="Code couleur pour l'affichage")
    icone = models.CharField(max_length=50, blank=True, help_text="Icône pour l'affichage")

    actif = models.BooleanField(default=True)
    ordre = models.PositiveSmallIntegerField(default=0)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ordre", "nom"]
        verbose_name = "Type de chambre"
        verbose_name_plural = "Types de chambres"

    def __str__(self):
        return f"{self.nom} ({self.code})"

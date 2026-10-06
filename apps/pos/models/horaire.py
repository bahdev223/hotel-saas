from django.db import models
from django.db.models import F, Q


class HoraireAffectation(models.Model):
    class JourSemaine(models.IntegerChoices):
        LUNDI = 0, "Lundi"
        MARDI = 1, "Mardi"
        MERCREDI = 2, "Mercredi"
        JEUDI = 3, "Jeudi"
        VENDREDI = 4, "Vendredi"
        SAMEDI = 5, "Samedi"
        DIMANCHE = 6, "Dimanche"

    affectation = models.ForeignKey(
        "pos.AffectationPointVente",
        on_delete=models.CASCADE,
        related_name="horaires",
    )
    jour_semaine = models.PositiveSmallIntegerField(choices=JourSemaine.choices)
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    date_debut = models.DateField(null=True, blank=True)
    date_fin = models.DateField(null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "pos_horaires_affectation"
        verbose_name = "Horaire d'affectation POS"
        verbose_name_plural = "Horaires d'affectation POS"
        ordering = ["affectation_id", "jour_semaine", "heure_debut"]
        constraints = [
            models.UniqueConstraint(
                fields=["affectation", "jour_semaine", "heure_debut", "heure_fin"],
                name="unique_horaire_pos_affectation",
            ),
            models.CheckConstraint(
                condition=~Q(heure_debut=F("heure_fin")),
                name="horaire_pos_debut_fin_differents",
            ),
        ]

    def __str__(self):
        return (
            f"{self.affectation.employe} - {self.get_jour_semaine_display()} "
            f"{self.heure_debut:%H:%M}-{self.heure_fin:%H:%M}"
        )

    @property
    def traverse_minuit(self):
        return self.heure_fin <= self.heure_debut

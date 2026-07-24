from django.db import models
from django.conf import settings
import uuid


def generate_sejour_code():
    return f"SEJ{uuid.uuid4().hex[:8].upper()}"


class Sejour(models.Model):
    class StatutSejour(models.TextChoices):
        PREVU = "PREVU", "Prévu"
        CHECK_IN = "CHECK_IN", "Check-in effectué"
        EN_COURS = "EN_COURS", "En cours"
        PROLONGE = "PROLONGE", "Prolongé"
        CHECK_OUT = "CHECK_OUT", "Check-out effectué"
        CLOTURE = "CLOTURE", "Clôturé"
        ANNULE = "ANNULE", "Annulé"

    code = models.CharField(max_length=50, unique=True, default=generate_sejour_code, editable=False)
    etablissement = models.ForeignKey(
        "entreprises.Etablissement",
        on_delete=models.PROTECT,
        related_name="sejours",
    )
    reservation = models.ForeignKey(
        "hotel.Reservation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sejours",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="sejours",
    )
    chambre = models.ForeignKey(
        "hotel.UniteModel",
        on_delete=models.PROTECT,
        related_name="sejours",
    )
    date_arrivee = models.DateTimeField()
    date_depart = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(
        max_length=30,
        choices=StatutSejour.choices,
        default=StatutSejour.EN_COURS,
    )
    nombre_adultes = models.PositiveSmallIntegerField(default=1)
    nombre_enfants = models.PositiveSmallIntegerField(default=0)
    montant_base = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_supplements = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    motif_annulation = models.TextField(blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="sejours_crees",
    )
    ferme_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="sejours_fermes",
    )
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Séjour"
        verbose_name_plural = "Séjours"
        ordering = ["-date_arrivee"]
        indexes = [
            models.Index(fields=["client", "statut"]),
            models.Index(fields=["chambre", "date_arrivee"]),
            models.Index(fields=["statut"]),
        ]

    def __str__(self):
        nom = getattr(self.client, "nom_complet", str(self.client))
        return f"{self.code} - {nom} - {self.chambre}"

    @property
    def duree_nuits(self):
        if not self.date_depart:
            return 0
        delta = self.date_depart - self.date_arrivee
        return max(1, delta.days)

    @property
    def est_actif(self):
        return self.statut in (
            self.StatutSejour.CHECK_IN,
            self.StatutSejour.EN_COURS,
            self.StatutSejour.PROLONGE,
        )

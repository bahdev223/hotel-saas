from django.db import models
from django.conf import settings
import uuid


def generate_reservation_code():
    return f"RES{uuid.uuid4().hex[:8].upper()}"


class Reservation(models.Model):
    class StatutReservation(models.TextChoices):
        BROUILLON = "BROUILLON", "Brouillon"
        EN_ATTENTE = "EN_ATTENTE", "En attente"
        OPTION = "OPTION", "Option"
        CONFIRMEE = "CONFIRMEE", "Confirmée"
        PARTIELLEMENT_PAYEE = "PARTIELLEMENT_PAYEE", "Partiellement payée"
        ANNULEE = "ANNULEE", "Annulée"
        NO_SHOW = "NO_SHOW", "Client non présenté"
        TRANSFORMEE = "TRANSFORMEE", "Transformée en séjour"

    code = models.CharField(max_length=50, unique=True, default=generate_reservation_code, editable=False)
    etablissement = models.ForeignKey(
        "entreprises.Etablissement",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    client = models.ForeignKey(
        "clients.Client",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    date_arrivee_prevue = models.DateTimeField()
    date_depart_prevue = models.DateTimeField()
    statut = models.CharField(
        max_length=30,
        choices=StatutReservation.choices,
        default=StatutReservation.CONFIRMEE,
    )
    nombre_adultes = models.PositiveSmallIntegerField(default=1)
    nombre_enfants = models.PositiveSmallIntegerField(default=0)
    montant_acompte = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    montant_total_estime = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    motif_annulation = models.TextField(blank=True)
    cree_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="reservations_crees",
    )
    annule_par = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reservations_annulees",
    )
    annule_le = models.DateTimeField(null=True, blank=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Réservation"
        verbose_name_plural = "Réservations"
        ordering = ["-date_arrivee_prevue"]
        indexes = [
            models.Index(fields=["client", "statut"]),
            models.Index(fields=["date_arrivee_prevue", "statut"]),
            models.Index(fields=["etablissement", "statut"]),
        ]

    def __str__(self):
        nom = getattr(self.client, "nom_complet", str(self.client))
        return f"{self.code} - {nom}"

    @property
    def duree_nuits(self):
        delta = self.date_depart_prevue - self.date_arrivee_prevue
        return max(1, delta.days)

    @property
    def est_annulable(self):
        return self.statut not in (self.StatutReservation.ANNULEE, self.StatutReservation.TRANSFORMEE)


class ReservationChambre(models.Model):
    reservation = models.ForeignKey(
        Reservation,
        on_delete=models.CASCADE,
        related_name="chambres_reservees",
    )
    chambre = models.ForeignKey(
        "hotel.UniteModel",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    tarif_source = models.ForeignKey(
        "hotel.TarifChambre",
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    type_tarif_nom = models.CharField(max_length=100)
    plan_tarifaire_nom = models.CharField(max_length=150)
    montant_unitaire = models.DecimalField(max_digits=12, decimal_places=2)
    quantite = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    montant_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        verbose_name = "Chambre réservée"
        verbose_name_plural = "Chambres réservées"

    def __str__(self):
        return f"{self.chambre} - {self.plan_tarifaire_nom} ({self.type_tarif_nom})"

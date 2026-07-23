# apps/hotel/models/location.py
from django.db import models
from django.utils import timezone
from decimal import Decimal
import uuid

def generate_location_id():
    return f"L{uuid.uuid4().hex[:8].upper()}"

class LocationModel(models.Model):
    TYPE_CHOICES = [
        ('CHAMBRE', 'Location chambre'),
        ('SALLE', 'Location salle'),
        ('ESPACE', "Location d'espace"),
        ('ESPACE_BAR', 'Location espace + bar'),
        ('BAR', 'Location bar VIP'),
    ]

    TARIF_CHOICES = [
        ('HEURE', 'Par heure'),
        ('JOUR', 'Par jour'),
    ]

    STATUT_CHOICES = [
        ('CONFIRMEE', 'Confirmée'),
        ('TERMINEE', 'Terminée'),
        ('ANNULEE', 'Annulée'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=generate_location_id, editable=False)
    client = models.ForeignKey('clients.Client', on_delete=models.PROTECT, related_name='locations')
    unite = models.ForeignKey('UniteModel', on_delete=models.PROTECT, related_name='locations')
    type_location = models.CharField(max_length=20, choices=TYPE_CHOICES, default='CHAMBRE')
    date_debut = models.DateTimeField()
    date_fin = models.DateTimeField()
    type_tarif = models.CharField(max_length=10, choices=TARIF_CHOICES, default='HEURE')
    montant_avance = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='CONFIRMEE')
    notes = models.TextField(blank=True, null=True)
    client_nom = models.CharField(max_length=200, blank=True, default='')
    client_telephone = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hotel_locations'
        verbose_name = 'Réservation'
        verbose_name_plural = 'Réservations'
        ordering = ['-date_debut']
        indexes = [
            models.Index(fields=['client', 'statut']),
            models.Index(fields=['unite', 'date_debut']),
            models.Index(fields=['type_location', 'statut']),
        ]

    def __str__(self):
        nom = self.client_nom or self.client.nom_complet
        return f"{self.unite.nom} - {nom}"

    @property
    def duree_heures(self):
        delta = self.date_fin - self.date_debut
        return max(1, int(delta.total_seconds() / 3600))

    @property
    def duree_display(self):
        h = self.duree_heures
        if h >= 24:
            jours = h // 24
            reste = h % 24
            if reste:
                return f"{jours}j {reste}h"
            return f"{jours}j"
        return f"{h}h"

    @property
    def reste_a_payer(self):
        if hasattr(self, 'facture') and self.facture:
            return self.facture.reste_a_payer
        return self.montant_total

    @property
    def duree_jours(self):
        return max(1, (self.duree_heures + 23) // 24)

    def calculer_montant_total(self):
        if self.type_tarif == 'JOUR' and self.unite.prix_jour:
            self.montant_total = self.unite.prix_jour * Decimal(str(self.duree_jours))
        else:
            self.montant_total = self.unite.prix * Decimal(str(self.duree_heures))
        self.save(update_fields=['montant_total'])
        return self.montant_total

    def terminer_auto(self):
        self.statut = 'TERMINEE'
        self.save(update_fields=['statut'])
        self.unite.liberer()

    def annuler(self):
        self.statut = 'ANNULEE'
        self.save(update_fields=['statut'])
        self.unite.liberer()
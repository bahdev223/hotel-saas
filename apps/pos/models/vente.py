# apps/pos/models/vente.py
import uuid
from decimal import Decimal
from django.db import models
from django.contrib.auth.models import User
from .point_vente import PointVente
from .session_caisse import SessionCaisse
from apps.tresorerie.models import Caisse
from apps.restaurant.models import TableModel
from apps.rh.models import Employe
from apps.clients.models import Client


def generate_vente_id():
    """Génère un ID unique pour la vente"""
    return f"V{uuid.uuid4().hex[:6].upper()}"


class Vente(models.Model):
    """Vente globale (table unique pour toutes les ventes)"""

    MODE_PAIEMENT_CHOICES = [
        ('ESPECES', 'Espèces'),
        ('CARTE', 'Carte bancaire'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CHEQUE', 'Chèque'),
        ('CREDIT', 'Crédit'),
        ('SOLDE', 'Solde client'),
        ('COMPTE_CLIENT', 'Compte client (hôtel)'),
        ('FACTURE', 'Facture globale'),
    ]

    STATUT_CHOICES = [
        ('EN_COURS', 'En cours'),
        ('PAYEE', 'Payée'),
        ('ANNULEE', 'Annulée'),
    ]

    id = models.CharField(max_length=20, primary_key=True, default=generate_vente_id)
    point_vente = models.ForeignKey(PointVente, on_delete=models.CASCADE, related_name='ventes')
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='ventes_pos')
    
    # Session de caisse associée
    session_caisse = models.ForeignKey(
        SessionCaisse, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ventes'
    )
    
    # Caissier qui a effectué la vente (EMPLOYÉ, pas User)
    caissier = models.ForeignKey(
        Employe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='ventes_effectuees'
    )

    numero = models.CharField(max_length=50, unique=True)
    table = models.ForeignKey(TableModel, on_delete=models.SET_NULL, null=True, blank=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventes')
    client_nom = models.CharField(max_length=200, blank=True, null=True)
    chambre_numero = models.CharField(max_length=20, blank=True, null=True)

    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    mode_paiement = models.CharField(max_length=20, choices=MODE_PAIEMENT_CHOICES, default='ESPECES')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')

    notes = models.TextField(blank=True, null=True)
    
    # 🔥 CORRIGÉ : Utiliser Employé au lieu de User
    encaisse_par = models.ForeignKey(
        Employe, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='ventes_encaissees'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pos_ventes'
        verbose_name = 'Vente'
        verbose_name_plural = 'Ventes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['session_caisse']),
            models.Index(fields=['caissier']),
            models.Index(fields=['encaisse_par']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        caissier_nom = self.caissier.nom_complet if self.caissier else "?"
        return f"{self.numero} - {self.montant_total} FCFA ({caissier_nom})"

    def calculer_total(self):
        total = self.lignes.aggregate(total=models.Sum('total_ligne'))['total'] or 0
        self.montant_total = total
        self.save(update_fields=['montant_total'])
        return total
    
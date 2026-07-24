from django.db import models
from decimal import Decimal
from django.utils import timezone
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse
from apps.restaurant.models import TableModel
from apps.clients.models import Client


def generate_vente_id():
    return f"V{timezone.now().strftime('%y%m%d%H%M%S%f')}"


class Vente(models.Model):
    MODE_PAIEMENT_CHOICES = [
        ('ESPECES', 'Esp\u00e8ces'), ('CARTE', 'Carte bancaire'),
        ('MOBILE_MONEY', 'Mobile Money'), ('CHEQUE', 'Ch\u00e8que'),
        ('CREDIT', 'Cr\u00e9dit'), ('SOLDE', 'Solde client'),
        ('COMPTE_CLIENT', 'Compte client'), ('FACTURE', 'Facture'),
    ]
    STATUT_CHOICES = [
        ('EN_COURS', 'En cours'), 
        ('PARTIELLEMENT_PAYEE', 'Partiellement payée'),
        ('PAYEE', 'Payée'), 
        ('ANNULEE', 'Annulée')
    ]

    id = models.CharField(max_length=20, primary_key=True, default=generate_vente_id)
    point_vente = models.ForeignKey('PointVente', on_delete=models.CASCADE, related_name='ventes')
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='ventes_pos')
    session_caisse = models.ForeignKey('SessionCaisse', on_delete=models.SET_NULL, null=True, blank=True, related_name='ventes')
    caissier = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventes_effectuees')
    serveur = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventes_servies')
    numero = models.CharField(max_length=50, unique=True)
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventes_pos')
    client_nom = models.CharField(max_length=200, blank=True, null=True)
    table = models.ForeignKey(TableModel, on_delete=models.SET_NULL, null=True, blank=True)
    chambre_numero = models.CharField(max_length=20, blank=True, null=True)
    sous_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Somme des prix catalogue")
    montant_remise = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_taxe = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Montant net à payer (sous_total - remise + taxe)")
    montant_paye = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant_restant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cout_revient_total = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Coût total des articles vendus")
    marge_totale = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Bénéfice net (montant_total - cout_revient_total)")
    mode_paiement = models.CharField(max_length=20, choices=MODE_PAIEMENT_CHOICES, default='ESPECES', help_text="Mode principal, utiliser PaiementVente pour les multi-paiements")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_COURS')
    notes = models.TextField(blank=True, null=True)
    encaisse_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='ventes_encaissees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pos_ventes'
        verbose_name = 'Vente'
        verbose_name_plural = 'Ventes'
        ordering = ['-created_at']

    def __str__(self):
        return f"Vente {self.numero} - {self.montant_total:,.0f} F"

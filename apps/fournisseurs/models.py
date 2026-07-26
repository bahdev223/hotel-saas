import uuid
from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from apps.comptabilite.models import CompteModel


def generate_id():
    return str(uuid.uuid4())[:8]


class Fournisseur(models.Model):
    id = models.CharField(max_length=50, primary_key=True, default=generate_id, editable=False)
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=200)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    contact = models.CharField(max_length=100, blank=True, null=True)
    identifiant_fiscal = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    actif = models.BooleanField(default=True)
    compte_comptable = models.ForeignKey(
        CompteModel, on_delete=models.PROTECT,
        null=True, blank=True, related_name='fournisseurs_comptes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock_fournisseurs'
        verbose_name = 'Fournisseur'
        verbose_name_plural = 'Fournisseurs'
        ordering = ['nom']

    def __str__(self):
        return f"{self.code} - {self.nom}"


class EcheanceFournisseur(models.Model):
    """Échéance de paiement due à un fournisseur."""

    STATUT_CHOICES = [
        ('ATTENTE', 'En attente'),
        ('PAYEE', 'Payée'),
        ('RETARD', 'En retard'),
        ('LETTREE', 'Lettrée'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=generate_id, editable=False)
    fournisseur = models.ForeignKey(
        Fournisseur,
        on_delete=models.PROTECT,
        related_name='echeances',
    )
    facture = models.ForeignKey(
        'facturation.FactureModel',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='echeances',
    )
    bon_entree = models.ForeignKey(
        'stock.BonEntree',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='echeances',
    )

    montant = models.DecimalField(max_digits=14, decimal_places=2, validators=[MinValueValidator(0)])
    montant_paye = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    date_echeance = models.DateField()
    date_paiement = models.DateField(null=True, blank=True)
    statut = models.CharField(max_length=10, choices=STATUT_CHOICES, default='ATTENTE')

    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'fournisseurs_echeances'
        verbose_name = 'Échéance fournisseur'
        verbose_name_plural = 'Échéances fournisseurs'
        ordering = ['date_echeance', 'created_at']

    def __str__(self):
        return f"{self.fournisseur.nom} - {self.montant} F due le {self.date_echeance}"

    @property
    def solde_restant(self):
        return self.montant - self.montant_paye

    @property
    def est_en_retard(self):
        from datetime import date
        return self.statut == 'ATTENTE' and self.date_echeance < date.today()

    def mettre_a_jour_statut(self):
        from datetime import date
        if self.montant_paye >= self.montant:
            self.statut = 'PAYEE'
            self.date_paiement = date.today()
        elif self.date_echeance < date.today():
            self.statut = 'RETARD'
        self.save()

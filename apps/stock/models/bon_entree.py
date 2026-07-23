from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid

from .fournisseur import Fournisseur
from .entrepot import Entrepot


class StatutBonEntree(models.TextChoices):
    BROUILLON = 'BROUILLON', 'Brouillon'
    VALIDE = 'VALIDE', 'Validé'
    PARTIEL = 'PARTIEL', 'Partiellement réceptionné'
    ANNULE = 'ANNULE', 'Annulé'


class BonEntree(models.Model):
    """Bon d'entrée / Bon de réception fournisseur"""
    
    # Identification
    numero = models.CharField(max_length=50, unique=True, verbose_name="Numéro bon d'entrée")
    reference_fournisseur = models.CharField(max_length=100, blank=True, null=True, verbose_name="Réf. fournisseur (facture)")
    
    # Liens
    fournisseur = models.ForeignKey(
        Fournisseur, 
        on_delete=models.PROTECT, 
        related_name='bons_entree',
        verbose_name="Fournisseur"
    )
    entrepot = models.ForeignKey(
        Entrepot, 
        on_delete=models.PROTECT,
        related_name='bons_entree',
        verbose_name="Entrepôt destination"
    )
    
    # Dates
    date_commande = models.DateField(verbose_name="Date commande", blank=True, null=True)
    date_reception = models.DateField(auto_now_add=True, verbose_name="Date réception")
    
    # Informations
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")
    transporteur = models.CharField(max_length=100, blank=True, null=True, verbose_name="Transporteur")
    numero_bl = models.CharField(max_length=100, blank=True, null=True, verbose_name="N° Bon de livraison")
    
    # Statut
    statut = models.CharField(
        max_length=20, 
        choices=StatutBonEntree.choices, 
        default=StatutBonEntree.BROUILLON,
        verbose_name="Statut"
    )
    
    # Total
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Total")
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bons_entree_crees',
        verbose_name="Créé par"
    )
    valide_at = models.DateTimeField(null=True, blank=True)
    valide_by = models.ForeignKey(
        'auth.User', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='bons_entree_valides',
        verbose_name="Validé par"
    )

    class Meta:
        db_table = 'stock_bons_entree'
        verbose_name = 'Bon d\'entrée'
        verbose_name_plural = 'Bons d\'entrée'
        ordering = ['-date_reception']

    def __str__(self):
        return f"{self.numero} - {self.fournisseur.nom} - {self.date_reception}"

    def save(self, *args, **kwargs):
        if not self.numero:
            from datetime import datetime
            self.numero = f"BE-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        super().save(*args, **kwargs)

    def calculer_totaux(self):
        total = Decimal('0')
        for ligne in self.lignes.all():
            total += ligne.montant
        self.total = total
        self.save()

    @property
    def est_valide(self):
        return self.statut == StatutBonEntree.VALIDE


class LigneBonEntree(models.Model):
    """Ligne de bon d'entrée"""
    
    bon_entree = models.ForeignKey(
        BonEntree, 
        on_delete=models.CASCADE, 
        related_name='lignes',
        verbose_name="Bon d'entrée"
    )
    produit = models.ForeignKey(
        'Produit', 
        on_delete=models.PROTECT,
        related_name='lignes_bon_entree',
        verbose_name="Produit"
    )
    
    # Quantités
    quantite_commandee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=1,
        validators=[MinValueValidator(0.01)],
        verbose_name="Quantité commandée"
    )
    quantite_recue = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Quantité reçue"
    )
    
    # Prix
    prix_achat = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0)],
        verbose_name="Prix d'achat unitaire"
    )
    
    # Montant (calculé)
    montant = models.DecimalField(max_digits=12, decimal_places=2, default=0, verbose_name="Montant")
    
    # Lot (optionnel)
    lot = models.ForeignKey(
        'Lot', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='lignes_bon_entree',
        verbose_name="Lot associé"
    )
    
    # Date péremption spécifique (peut différer du lot)
    date_peremption = models.DateField(null=True, blank=True, verbose_name="Date de péremption")
    
    # Notes
    notes = models.TextField(blank=True, null=True, verbose_name="Notes")

    class Meta:
        db_table = 'stock_bons_entree_lignes'
        verbose_name = 'Ligne de bon d\'entrée'
        verbose_name_plural = 'Lignes de bons d\'entrée'

    def save(self, *args, **kwargs):
        self.montant = self.quantite_recue * self.prix_achat
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.bon_entree.numero} - {self.produit.nom} - {self.quantite_recue}"

    @property
    def ecart(self):
        """Écart entre commandé et reçu"""
        return self.quantite_commandee - self.quantite_recue
    
# apps/facturation/models.py
from django.db import models
from django.utils import timezone
import uuid


def generate_facture_numero():
    """Génère un numéro de facture unique"""
    return f"F{timezone.now().strftime('%y%m%d')}{uuid.uuid4().hex[:4].upper()}"


from django.contrib.contenttypes.fields import GenericRelation
from apps.paiements.models import Paiement
from apps.clients.models import Client


class FactureModel(models.Model):
    """Facture - document financier simple (client ou fournisseur)"""
    
    TYPE_FACTURE_CHOICES = [
        ('CLIENT', 'Facture client'),
        ('FOURNISSEUR', 'Facture fournisseur'),
    ]
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EMISE', 'Émise'),
        ('PAYEE', 'Payée'),
        ('ANNULEE', 'Annulée'),
    ]
    
    # Identification
    id = models.CharField(max_length=50, primary_key=True, default=uuid.uuid4, editable=False)
    numero = models.CharField(max_length=20, unique=True, default=generate_facture_numero)
    type = models.CharField(max_length=20, choices=TYPE_FACTURE_CHOICES, default='CLIENT')
    
    # Image facture (obligatoire pour fournisseur)
    image = models.ImageField(upload_to='factures/', blank=True, null=True)
    
    # Liens
    location = models.OneToOneField(
        'hotel.LocationModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facture'
    )
    sejour = models.OneToOneField(
        'hotel.Sejour',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facture'
    )
    commande = models.OneToOneField(
        'pos.Commande',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facture'
    )
    bon_entree = models.OneToOneField(
        'stock.BonEntree',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='facture'
    )
    
    # Client / Fournisseur
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='factures')
    fournisseur = models.ForeignKey(
        'fournisseurs.Fournisseur', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='factures'
    )
    # Dénormalisé pour historique
    client_nom = models.CharField(max_length=200)
    client_contact = models.CharField(max_length=50, blank=True, default='', verbose_name='Contact client')
    
    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    
    # Dates
    date_emission = models.DateField(auto_now_add=True)
    
    # Métadonnées
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # 🔥 RELATION AVEC LES PAIEMENTS (via GenericRelation)
    paiements = GenericRelation('paiements.Paiement')
    
    class Meta:
        db_table = 'factures'
        verbose_name = 'Facture'
        verbose_name_plural = 'Factures'
        ordering = ['-date_emission']
        indexes = [
            models.Index(fields=['numero']),
            models.Index(fields=['statut']),
            models.Index(fields=['type']),
            models.Index(fields=['location']),
            models.Index(fields=['sejour']),
            models.Index(fields=['commande']),
        ]
    
    def __str__(self):
        return f"{self.numero} - {self.client_nom}"
    
    @property
    def type_facture(self):
        """Type de facture: COMMANDE, SEJOUR, LOCATION, ou MANUELLE"""
        if self.commande_id:
            return 'COMMANDE'
        if self.sejour_id:
            return 'SEJOUR'
        if self.location_id:
            return 'LOCATION'
        return 'MANUELLE'

    @property
    def total_ht(self):
        """Total HT depuis les lignes"""
        return sum(l.total_ht for l in self.lignes.all())

    @property
    def total_tva(self):
        """Total TVA depuis les lignes"""
        return sum(l.total_tva for l in self.lignes.all())

    @property
    def montant_total(self):
        """Calcul automatique du total TTC depuis les lignes"""
        return self.total_ht + self.total_tva
    
    @property
    def total_paye(self):
        """Total payé depuis les paiements liés"""
        return sum(p.montant for p in self.paiements.filter(statut='VALIDE', sens='ENTREE'))
    
    @property
    def reste_a_payer(self):
        return self.montant_total - self.total_paye
    
    @property
    def est_payee(self):
        return self.reste_a_payer <= 0
    
    def emettre(self):
        """Émettre la facture (BROUILLON → EMISE)"""
        if self.statut == 'BROUILLON':
            self.statut = 'EMISE'
            self.save()
            return True
        return False
    
    def annuler(self):
        """Annuler la facture"""
        self.statut = 'ANNULEE'
        self.save()
    
    def marquer_payee(self):
        """Marquer comme payée (force le statut)"""
        if self.reste_a_payer <= 0:
            self.statut = 'PAYEE'
            self.save()
            return True
        return False
    

class LigneFactureModel(models.Model):
    """Ligne de facture - ce qui est facturé"""
    
    id = models.CharField(max_length=50, primary_key=True, default=uuid.uuid4, editable=False)
    facture = models.ForeignKey(FactureModel, on_delete=models.CASCADE, related_name='lignes')
    
    description = models.CharField(max_length=200)
    quantite = models.DecimalField(max_digits=10, decimal_places=2, default=1)
    prix_unitaire = models.DecimalField(max_digits=10, decimal_places=2)
    
    # TVA par défaut 18% (Mali)
    tva = models.DecimalField(max_digits=5, decimal_places=2, default=18)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'factures_lignes'
        verbose_name = 'Ligne de facture'
        verbose_name_plural = 'Lignes de facture'
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.description} - {self.quantite} x {self.prix_unitaire:,.0f} F"
    
    @property
    def total_ht(self):
        return self.quantite * self.prix_unitaire
    
    @property
    def total_tva(self):
        return self.total_ht * (self.tva / 100)
    
    @property
    def total_ttc(self):
        return self.total_ht + self.total_tva
    
    def save(self, *args, **kwargs):
        """Sauvegarde et met à jour le total de la facture"""
        super().save(*args, **kwargs)
        # Optionnel: mettre à jour le montant total sur la location ?
        # Non, la location ne doit pas être modifiée par la facture
        
        
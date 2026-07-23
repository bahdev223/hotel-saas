# apps/pos/models/commande.py
from django.db import models
from django.utils import timezone
import uuid

from .vente import Vente
from .point_vente import PointVente
from apps.restaurant.models import TableModel
from apps.clients.models import Client


def generate_commande_numero():
    """Génère un numéro de commande unique"""
    return f"C{timezone.now().strftime('%y%m%d')}{uuid.uuid4().hex[:4].upper()}"


class Commande(models.Model):
    """Commande client avec suivi cuisine"""
    
    TYPE_CHOICES = [
        ('SUR_PLACE', 'Sur place'),
        ('EMPORTER', 'À emporter'),
        ('LIVRAISON', 'Livraison'),
    ]
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_PREPARATION', 'En préparation'),
        ('PRETE', 'Prête'),
        ('EN_COURS_DE_LIVRAISON', 'En cours de livraison'),
        ('SERVIE', 'Servie'),
        ('LIVREE', 'Livrée'),
        ('PAYEE', 'Payée'),
        ('ANNULEE', 'Annulée'),
    ]
    
    # Identification
    numero = models.CharField(max_length=20, unique=True, default=generate_commande_numero)
    point_vente = models.ForeignKey(PointVente, on_delete=models.CASCADE, related_name='commandes')
    entrepot = models.ForeignKey('stock.Entrepot', on_delete=models.SET_NULL, null=True, blank=True, related_name='commandes')
    
    # Type et statut
    type_commande = models.CharField(max_length=20, choices=TYPE_CHOICES, default='SUR_PLACE')
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default='EN_ATTENTE')
    
    # Client
    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='commandes')
    client_nom = models.CharField(max_length=200, blank=True)
    client_telephone = models.CharField(max_length=20, blank=True)
    adresse_livraison = models.TextField(blank=True)
    
    # Table (si sur place) — déprécié, plus utilisé
    table = models.ForeignKey(TableModel, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Lien avec la vente (optionnel)
    vente = models.OneToOneField(Vente, on_delete=models.SET_NULL, null=True, blank=True, related_name='commande')
    
    # ❌ LIGNE SUPPRIMÉE : plus de JSONField lignes
    
    # Montants
    montant_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    frais_livraison = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Timing
    date_commande = models.DateTimeField(auto_now_add=True)
    date_preparation = models.DateTimeField(null=True, blank=True)
    date_service = models.DateTimeField(null=True, blank=True)
    
    # Métadonnées
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey('rh.Employe', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pos_commandes'
        verbose_name = 'Commande'
        verbose_name_plural = 'Commandes'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['statut']),
            models.Index(fields=['point_vente', 'statut']),
            models.Index(fields=['numero']),
        ]
    
    def __str__(self):
        return f"{self.numero} - {self.get_type_commande_display()} - {self.get_statut_display()}"
    
    @property
    def temps_attente_minutes(self):
        """Temps d'attente depuis la commande"""
        if self.date_preparation:
            delta = self.date_preparation - self.date_commande
            return int(delta.total_seconds() / 60)
        delta = timezone.now() - self.date_commande
        return int(delta.total_seconds() / 60)
    
    def passer_en_preparation(self):
        """Passer la commande en préparation"""
        self.statut = 'EN_PREPARATION'
        self.date_preparation = timezone.now()
        self.save()
    
    def marquer_prete(self):
        """Marquer la commande comme prête"""
        self.statut = 'PRETE'
        self.save()
    
    def servir(self):
        """Servir la commande (sur place)"""
        self.statut = 'SERVIE'
        self.date_service = timezone.now()
        self.save()
    
    def demarrer_livraison(self):
        """Marquer la commande en cours de livraison"""
        self.statut = 'EN_COURS_DE_LIVRAISON'
        self.date_service = timezone.now()
        self.save()
    
    def livrer(self):
        """Livrer la commande (livraison)"""
        self.statut = 'LIVREE'
        self.save()
    
    def annuler(self):
        """Annuler la commande"""
        self.statut = 'ANNULEE'
        self.save()
        
            
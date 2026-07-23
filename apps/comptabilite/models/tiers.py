# apps/comptabilite/models/tiers.py

from django.db import models
from .compte import CompteModel


class TiersModel(models.Model):
    """Tiers (clients, fournisseurs, personnel, état)"""
    
    TYPE_CHOICES = [
        ('CLIENT', 'Client'),
        ('FOURNISSEUR', 'Fournisseur'),
        ('PERSONNEL', 'Personnel'),
        ('ETAT', 'État'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    
    type_tiers = models.CharField(max_length=20, choices=TYPE_CHOICES)
    
    # 🔥 LIAISON COMPTABLE (IMPORTANT)
    compte = models.ForeignKey(
        CompteModel,
        on_delete=models.PROTECT,  # ⚠️ PROTECT > CASCADE ici
        related_name='tiers'
    )
    
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    identifiant_fiscal = models.CharField(max_length=50, blank=True, null=True)
    
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'compta_tiers'
        verbose_name = 'Tiers'
        verbose_name_plural = 'Tiers'
        ordering = ['code']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    # ✅ Helpers métier
    @property
    def est_client(self):
        return self.type_tiers == "CLIENT"
    
    @property
    def est_fournisseur(self):
        return self.type_tiers == "FOURNISSEUR"
    
    
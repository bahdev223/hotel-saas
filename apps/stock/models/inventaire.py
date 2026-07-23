# apps/stock/models/inventaire.py
from django.db import models
from django.utils import timezone
from decimal import Decimal


class Inventaire(models.Model):
    """Session d'inventaire"""
    
    STATUS_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('VALIDE', 'Validé'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    entrepot = models.ForeignKey('Entrepot', on_delete=models.CASCADE, related_name='inventaires')
    date_debut = models.DateTimeField(auto_now_add=True)
    date_fin = models.DateTimeField(null=True, blank=True)
    statut = models.CharField(max_length=20, choices=STATUS_CHOICES, default='BROUILLON')
    realise_par = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock_inventaires'
        verbose_name = 'Inventaire'
        verbose_name_plural = 'Inventaires'
        ordering = ['-date_debut']
    
    def __str__(self):
        return f"{self.code} - {self.entrepot.nom} - {self.date_debut.strftime('%d/%m/%Y')}"
    
    @property
    def est_termine(self):
        return self.statut in ['TERMINE', 'VALIDE']
    
    @property
    def total_ecart(self):
        return self.lignes.aggregate(total=models.Sum('ecart'))['total'] or 0


class LigneInventaire(models.Model):
    """Ligne d'inventaire pour un produit"""
    
    inventaire = models.ForeignKey(Inventaire, on_delete=models.CASCADE, related_name='lignes')
    produit = models.ForeignKey('Produit', on_delete=models.CASCADE)
    quantite_theorique = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    quantite_reelle = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    prix_unitaire = models.DecimalField(max_digits=15, decimal_places=2, default=0, verbose_name="Prix d'achat unitaire")
    ecart = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'stock_inventaires_lignes'
        unique_together = ['inventaire', 'produit']
    
    def __str__(self):
        return f"{self.produit.nom}: {self.quantite_reelle}/{self.quantite_theorique}"
    
    def save(self, *args, **kwargs):
        self.ecart = self.quantite_reelle - self.quantite_theorique
        super().save(*args, **kwargs)
        
        
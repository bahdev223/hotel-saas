from decimal import Decimal
from django.db import models
from .produit import Produit
from .entrepot import Entrepot


class MouvementStock(models.Model):
    """Mouvement de stock"""

    TYPE_MOUVEMENT_CHOICES = [
        ('ENTREE', 'Entrée'),
        ('SORTIE', 'Sortie'),
        ('TRANSFERT', 'Transfert'),
        ('INITIALISATION', 'Initialisation'),
    ]

    MOTIF_CHOICES = [
        ('achat', 'Achat'),
        ('vente', 'Vente'),
        ('consommation', 'Consommation'),
        ('perte', 'Perte'),
        ('production', 'Production'),
        ('reapprovisionnement', 'Réapprovisionnement'),
        ('inventaire', 'Inventaire'),
        ('stock_initial', 'Stock initial'),
    ]

    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement = models.CharField(max_length=20, choices=TYPE_MOUVEMENT_CHOICES, default='ENTREE')
    motif = models.CharField(max_length=30, choices=MOTIF_CHOICES, default='achat')
    quantite = models.DecimalField(max_digits=10, decimal_places=2)
    valeur_unitaire = models.DecimalField(max_digits=10, decimal_places=2, default=0,
        help_text="Prix unitaire au moment du mouvement")
    valeur_total = models.DecimalField(max_digits=15, decimal_places=2, default=0,
        help_text="Quantite x valeur unitaire")
    entrepot_source = models.ForeignKey(Entrepot, on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_source')
    entrepot_dest = models.ForeignKey(Entrepot, on_delete=models.SET_NULL, null=True, blank=True, related_name='mouvements_dest')
    reference = models.CharField(max_length=100, blank=True, null=True,
        help_text="Reference de la piece source (CMD-00045, FACT-001, etc.)")
    raison = models.CharField(max_length=200, blank=True)
    utilisateur = models.CharField(max_length=100)
    date_mouvement = models.DateTimeField(auto_now_add=True)
    unite_texte = models.CharField(max_length=100, blank=True, null=True)

    ecriture = models.ForeignKey(
        'comptabilite.EcritureModel',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='mouvements_stock'
    )

    class Meta:
        db_table = 'stock_mouvements'
        verbose_name = 'Mouvement de stock'
        verbose_name_plural = 'Mouvements de stock'
        ordering = ['-date_mouvement']

    def __str__(self):
        return f"{self.produit.nom} - {self.get_type_mouvement_display()} ({self.get_motif_display()}) - {self.quantite}"

    def save(self, *args, **kwargs):
        self.valeur_total = Decimal(str(self.quantite)) * Decimal(str(self.valeur_unitaire))
        super().save(*args, **kwargs)

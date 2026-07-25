# apps/stock/models/mouvement_lot.py
from django.db import models
from django.db.models import Q, CheckConstraint
from decimal import Decimal
from .lot import LotProduit
from .mouvement import MouvementStock

class MouvementLot(models.Model):
    """Liaison entre un mouvement de stock global et les lots impactés."""
    
    mouvement = models.ForeignKey(MouvementStock, on_delete=models.PROTECT, related_name='mouvements_lots')
    lot = models.ForeignKey(LotProduit, on_delete=models.PROTECT, related_name='mouvements')
    quantite = models.DecimalField(
        max_digits=18, decimal_places=4,
        help_text="Quantité signée : positive pour une entrée, négative pour une sortie."
    )
    
    class Meta:
        db_table = 'stock_mouvement_lot'
        verbose_name = 'Mouvement de Lot'
        verbose_name_plural = 'Mouvements de Lots'
        constraints = [
            CheckConstraint(
                condition=~Q(quantite=0),
                name="mouvement_lot_quantite_non_nulle",
            )
        ]
        
    def __str__(self):
        return f"{self.mouvement.type_mouvement} - Lot {self.lot.numero} ({self.quantite})"

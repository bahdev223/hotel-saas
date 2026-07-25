from django.db import models
from django.conf import settings

class JournalStock(models.Model):
    """Journal immuable des mouvements de stock"""
    
    mouvement = models.OneToOneField(
        'stock.MouvementStock',
        on_delete=models.PROTECT,
        related_name="journal",
    )
    produit = models.ForeignKey(
        'stock.Produit',
        on_delete=models.PROTECT,
        related_name="historique_journal"
    )
    entrepot = models.ForeignKey(
        'stock.Entrepot',
        on_delete=models.PROTECT,
        related_name="historique_journal"
    )
    stock_avant = models.DecimalField(
        max_digits=18,
        decimal_places=4,
    )
    quantite_mouvement = models.DecimalField(
        max_digits=18,
        decimal_places=4,
    )
    stock_apres = models.DecimalField(
        max_digits=18,
        decimal_places=4,
    )
    cout_unitaire = models.DecimalField(
        max_digits=18,
        decimal_places=4,
        default=0,
    )
    valeur_mouvement = models.DecimalField(
        max_digits=18,
        decimal_places=2,
        default=0,
    )
    effectue_par = models.CharField(
        max_length=100,
        blank=True,
        null=True
    )
    effectue_par_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    cree_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_journal'
        verbose_name = 'Entrée au journal de stock'
        verbose_name_plural = 'Journal de stock'
        ordering = ['-cree_le']
        indexes = [
            models.Index(fields=['produit', 'entrepot', '-cree_le']),
        ]

    def __str__(self):
        return f"{self.produit.nom} | {self.quantite_mouvement} | {self.cree_le.strftime('%d/%m/%Y %H:%M')}"

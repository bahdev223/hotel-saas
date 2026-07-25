from django.db import models
from django.conf import settings

def generate_transfert_id():
    import uuid
    return f"TR-{uuid.uuid4().hex[:8].upper()}"

class TransfertStock(models.Model):
    """Transfert de stock entre deux entrepôts"""
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('VALIDE', 'Validé'),
        ('ANNULE', 'Annulé'),
    ]

    numero = models.CharField(max_length=50, primary_key=True, default=generate_transfert_id, editable=False)
    entrepot_source = models.ForeignKey('stock.Entrepot', on_delete=models.PROTECT, related_name='transferts_sortants')
    entrepot_dest = models.ForeignKey('stock.Entrepot', on_delete=models.PROTECT, related_name='transferts_entrants')
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='VALIDE')
    
    source_operation = models.OneToOneField('stock.SourceOperation', on_delete=models.PROTECT, null=True, blank=True)
    
    cree_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='transferts_crees', null=True)
    valide_par = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='transferts_valides', null=True, blank=True)
    
    date_creation = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)

    class Meta:
        db_table = 'stock_transfert'
        verbose_name = 'Transfert de stock'
        verbose_name_plural = 'Transferts de stock'

    def __str__(self):
        return f"{self.numero} ({self.entrepot_source.nom} -> {self.entrepot_dest.nom})"


class LigneTransfertStock(models.Model):
    """Ligne de transfert"""
    transfert = models.ForeignKey(TransfertStock, on_delete=models.PROTECT, related_name='lignes')
    produit = models.ForeignKey('stock.Produit', on_delete=models.PROTECT)
    quantite = models.DecimalField(max_digits=18, decimal_places=4)
    unite_mesure = models.ForeignKey('stock.UniteMesure', on_delete=models.PROTECT, null=True, blank=True)
    
    class Meta:
        db_table = 'stock_ligne_transfert'
        verbose_name = 'Ligne de transfert'
        verbose_name_plural = 'Lignes de transfert'
        
    def __str__(self):
        return f"{self.transfert.numero} - {self.produit.nom} ({self.quantite})"

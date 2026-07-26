# apps/stock/models/politique_stock.py
from django.db import models


class PolitiqueStockRestaurant(models.Model):
    MODE_CONSOMMATION_CHOICES = [
        ('AUTO', 'Automatique'),
        ('MANUEL', 'Manuel'),
        ('DIFFERE', 'Différé'),
    ]

    EVENEMENT_CHOICES = [
        ('PAIEMENT', 'Au paiement'),
        ('VALIDATION', 'À la validation de commande'),
        ('CLOTURE', 'À la clôture de caisse'),
        ('MANUEL', 'Déclenchement manuel'),
    ]

    etablissement = models.ForeignKey(
        'entreprises.Etablissement',
        on_delete=models.CASCADE,
        related_name='politiques_stock',
        null=True,
        blank=True,
        help_text="Établissement concerné (null = valeur par défaut)"
    )
    point_vente = models.ForeignKey(
        'pos.PointVente',
        on_delete=models.CASCADE,
        related_name='politiques_stock',
        null=True,
        blank=True,
        help_text="Point de vente concerné (null = valeur par défaut de l'établissement)"
    )
    entrepot_source = models.ForeignKey(
        'stock.Entrepot',
        on_delete=models.PROTECT,
        related_name='politiques_restaurant',
        help_text="Entrepôt utilisé pour le déstockage"
    )
    mode_consommation = models.CharField(
        max_length=10,
        choices=MODE_CONSOMMATION_CHOICES,
        default='AUTO',
        help_text="Quand la consommation est-elle déclenchée"
    )
    evenement_declencheur = models.CharField(
        max_length=10,
        choices=EVENEMENT_CHOICES,
        default='PAIEMENT',
        help_text="Événement qui déclenche la consommation"
    )
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock_politique_stock_restaurant'
        verbose_name = 'Politique de stock restaurant'
        verbose_name_plural = 'Politiques de stock restaurant'
        unique_together = [
            ('etablissement', 'point_vente'),
        ]

    def __str__(self):
        pv = f"PV:{self.point_vente.nom}" if self.point_vente else "Tous"
        etab = f"Ets:{self.etablissement.nom}" if self.etablissement else "Défaut"
        return f"Politique {etab}/{pv} - {self.get_mode_consommation_display()}/{self.get_evenement_declencheur_display()}"

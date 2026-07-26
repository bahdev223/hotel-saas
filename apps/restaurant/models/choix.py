from decimal import Decimal
from django.db import models
from .menu import LigneMenuModel
from .recette import RecetteModel


class ChoixLigneCommande(models.Model):
    """Snapshot du choix client pour une ligne de commande menu avec type_ligne=CHOIX"""

    GROUPE_CHOICES = [
        ('ENTREE', 'Entrée'),
        ('PLAT', 'Plat principal'),
        ('ACCOMPAGNEMENT', 'Accompagnement'),
        ('BOISSON', 'Boisson'),
        ('DESSERT', 'Dessert'),
    ]

    ligne_commande = models.ForeignKey(
        'pos.LigneCommande',
        on_delete=models.CASCADE,
        related_name='choix_menu'
    )
    groupe = models.CharField(max_length=20, choices=GROUPE_CHOICES)
    recette = models.ForeignKey(
        RecetteModel,
        on_delete=models.PROTECT,
        related_name='choix_commandes'
    )
    ligne_menu = models.ForeignKey(
        LigneMenuModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='choix_commandes'
    )
    quantite = models.IntegerField(default=1)
    prix_supplement = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    class Meta:
        db_table = 'restaurant_choix_ligne_commande'
        verbose_name = 'Choix client (menu)'
        verbose_name_plural = 'Choix clients (menus)'

    def __str__(self):
        return f"[{self.groupe}] {self.recette.nom} x{self.quantite}"

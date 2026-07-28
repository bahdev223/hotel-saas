from django.db import models
from .ligne_vente import LigneVente
from apps.restaurant.models import RecetteModel


class LigneVenteComposition(models.Model):
    GROUPE_CHOICES = [
        ('ENTREE', 'Entrée'),
        ('PLAT', 'Plat'),
        ('ACCOMPAGNEMENT', 'Accompagnement'),
        ('BOISSON', 'Boisson'),
        ('DESSERT', 'Dessert'),
        ('SUPPLEMENT', 'Supplément'),
    ]

    ligne_vente = models.ForeignKey(
        LigneVente,
        on_delete=models.CASCADE,
        related_name='compositions'
    )
    groupe = models.CharField(max_length=20, choices=GROUPE_CHOICES)
    recette = models.ForeignKey(
        RecetteModel,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
    )
    nom_snapshot = models.CharField(max_length=200, blank=True, default='')
    quantite = models.IntegerField(default=1)
    prix_supplement = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cout_unitaire_snapshot = models.DecimalField(max_digits=18, decimal_places=4, default=0)

    class Meta:
        db_table = 'pos_lignes_vente_composition'
        verbose_name = 'Composition de ligne de vente'
        verbose_name_plural = 'Compositions de lignes de vente'

    def __str__(self):
        return f"{self.nom_snapshot or self.recette} x{self.quantite}"

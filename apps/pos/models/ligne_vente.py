# apps/pos/models/ligne_vente.py

from django.db import models

from .vente import Vente
from apps.stock.models import Produit
from apps.restaurant.models import MenuModel, RecetteModel


class LigneVente(models.Model):
    """Ligne de vente POS"""

    vente = models.ForeignKey(
        Vente,
        on_delete=models.CASCADE,
        related_name='lignes'
    )

    # Vente directe (Coca, Eau, etc.)
    produit = models.ForeignKey(
        Produit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Vente restaurant (Riz gras, Pizza, etc.)
    menu = models.ForeignKey(
        MenuModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    # Optionnel : recette exacte choisie
    recette = models.ForeignKey(
        RecetteModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    quantite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1
    )

    prix_unitaire = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pos_lignes_vente'
        verbose_name = 'Ligne de vente'
        verbose_name_plural = 'Lignes de vente'

    def __str__(self):

        if self.produit:
            nom = self.produit.nom

        elif self.menu:
            nom = self.menu.nom

        else:
            nom = "Article inconnu"

        return f"{self.quantite} x {nom}"

    @property
    def total_ligne(self):
        return float(self.quantite) * float(self.prix_unitaire)

    @property
    def article_nom(self):

        if self.produit:
            return self.produit.nom

        if self.menu:
            return self.menu.nom

        return "Inconnu"

    @property
    def type_article(self):

        if self.produit:
            return "PRODUIT"

        if self.menu:
            return "MENU"

        return "INCONNU"
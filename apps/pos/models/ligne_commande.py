# apps/pos/models/ligne_commande.py
from django.db import models
from .commande import Commande
from apps.stock.models import Produit
from apps.restaurant.models import MenuModel, RecetteModel
from apps.hotel.models.unite import UniteModel


class LigneCommande(models.Model):
    """Ligne de commande POS (pour le suivi cuisine)"""

    commande = models.ForeignKey(
        Commande,
        on_delete=models.CASCADE,
        related_name='lignes'
    )

    # Produit ou Menu
    produit = models.ForeignKey(
        Produit,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

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

    # Unité (chambre/salle) pour les réservations hôtel
    unite = models.ForeignKey(
        UniteModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    heures = models.PositiveIntegerField(
        default=1,
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
        db_table = 'pos_lignes_commande'
        verbose_name = 'Ligne de commande'
        verbose_name_plural = 'Lignes de commande'

    def __str__(self):
        if self.unite:
            return f"{self.heures}h {self.unite.nom}"
        if self.produit:
            nom = self.produit.nom
        elif self.menu:
            nom = self.menu.nom
        else:
            nom = "Article inconnu"
        return f"{self.quantite} x {nom}"

    @property
    def total_ligne(self):
        if self.unite:
            return float(self.heures or 1) * float(self.prix_unitaire)
        return float(self.quantite) * float(self.prix_unitaire)

    @property
    def article_nom(self):
        if self.unite:
            return self.unite.nom
        if self.produit:
            return self.produit.nom
        if self.menu:
            return self.menu.nom
        return "Inconnu"

    @property
    def type_article(self):
        if self.unite:
            return "LOCATION"
        if self.produit:
            return "PRODUIT"
        if self.menu:
            return "MENU"
        return "INCONNU"
    
    
    
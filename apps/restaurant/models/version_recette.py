# apps/restaurant/models/version_recette.py
import uuid
from decimal import Decimal
from django.db import models
from apps.stock.models import Produit


def generate_version_recette_id():
    return f"VR-{uuid.uuid4().hex[:8].upper()}"


class VersionRecette(models.Model):

    class Statut(models.TextChoices):
        BROUILLON = 'BROUILLON', 'Brouillon'
        A_VALIDER = 'A_VALIDER', 'À valider'
        ACTIVE = 'ACTIVE', 'Active'
        ARCHIVEE = 'ARCHIVEE', 'Archivée'
    """Version figée d'une recette à un instant T.

    Une fois ACTIVE, les ingrédients et leurs quantités ne peuvent plus
    être modifiés (la recette originale peut continuer d'évoluer en brouillon).
    """

    id = models.CharField(max_length=50, primary_key=True, default=generate_version_recette_id, editable=False)
    recette = models.ForeignKey(
        'restaurant.RecetteModel',
        on_delete=models.CASCADE,
        related_name='versions'
    )
    numero_version = models.PositiveIntegerField(
        help_text="Numéro de version incrémental pour cette recette"
    )

    statut = models.CharField(
        max_length=20,
        choices=Statut.choices,
        default=Statut.BROUILLON,
    )

    # Snapshots des champs de la recette
    nom_snapshot = models.CharField(max_length=100)
    type_recette_snapshot = models.CharField(max_length=20)
    rendement_quantite_snapshot = models.DecimalField(
        max_digits=10, decimal_places=2, null=True, blank=True
    )
    produit_fini_snapshot = models.ForeignKey(
        Produit, on_delete=models.SET_NULL, null=True, blank=True
    )

    # Métadonnées
    notes = models.TextField(blank=True, null=True)
    cree_par = models.CharField(max_length=150, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'restaurant_version_recette'
        verbose_name = 'Version de recette'
        verbose_name_plural = 'Versions de recettes'
        unique_together = [('recette', 'numero_version')]
        ordering = ['recette', '-numero_version']

    def __str__(self):
        return f"{self.recette.nom} v{self.numero_version} ({self.get_statut_display()})"

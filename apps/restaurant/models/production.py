# apps/restaurant/models/production.py
from decimal import Decimal
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from .recette import RecetteModel
from apps.stock.models import Produit, StockEntrepot, Entrepot

class Production(models.Model):
    """Production en cuisine - préparation de recettes"""
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('VALIDE', 'Validé'),
        ('ANNULE', 'Annulé'),
    ]
    
    # Identification
    numero = models.CharField(max_length=20, unique=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    date_production = models.DateField(null=True, blank=True, help_text="Date prévue de production")
    
    # Responsables
    produit_par = models.ForeignKey(
        'rh.Employe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productions'
    )
    valide_par = models.ForeignKey(
        'rh.Employe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productions_validees'
    )
    
    # Liens entrepôts
    entrepot_source = models.ForeignKey(
        'stock.Entrepot',
        on_delete=models.SET_NULL,
        null=True,
        related_name='productions_sorties'
    )
    entrepot_dest = models.ForeignKey(
        'stock.Entrepot',
        on_delete=models.SET_NULL,
        null=True,
        related_name='productions_entrees'
    )
    
    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    
    # Métadonnées
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'restaurant_productions'
        verbose_name = 'Production'
        verbose_name_plural = 'Productions'
        ordering = ['-date']
    
    def save(self, *args, **kwargs):
        if not self.numero:
            import uuid
            self.numero = f"PRD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Production #{self.numero} - {self.date.strftime('%d/%m/%Y')}"
    
    @property
    def total_unites(self):
        """Total des unités planifiées"""
        return sum(l.quantite for l in self.lignes.all())

    @property
    def total_unites_reelles(self):
        """Total des unités réellement produites"""
        return sum(l.quantite_reelle or l.quantite for l in self.lignes.all())

    @property
    def cout_theorique(self):
        """Coût théorique total (somme des coûts par recette * quantité planifiée)"""
        total = Decimal('0')
        for l in self.lignes.select_related('recette').all():
            if l.recette:
                total += l.recette.cout_ingredients * l.quantite
        return total

    @property
    def cout_reel_total(self):
        """Coût réel total (somme des ingrédients consommés valorisés au CUMP)"""
        total = self.ingredients.aggregate(
            total=Sum(
                models.F('quantite') * models.F('produit__stockentrepot__prix_achat'),
                output_field=models.DecimalField()
            )
        )['total'] or Decimal('0')
        return total

    @property
    def ecart_cout(self):
        """Écart coût réel - coût théorique (positif = dépassement)"""
        return self.cout_reel_total - self.cout_theorique
    



class ProductionLigne(models.Model):
    """Ligne de production - une recette produite"""
    
    production = models.ForeignKey(
        Production,
        on_delete=models.CASCADE,
        related_name='lignes'
    )
    recette = models.ForeignKey(
        RecetteModel,
        on_delete=models.CASCADE,
        related_name='productions'
    )
    quantite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1
    )
    quantite_reelle = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Quantité réellement produite (remplie après production)"
    )
    cout_reel_ligne = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Coût réel des ingrédients consommés pour cette ligne"
    )

    class Meta:
        db_table = 'restaurant_production_lignes'
        verbose_name = 'Ligne de production'
        verbose_name_plural = 'Lignes de production'
    
    def __str__(self):
        return f"{self.quantite} x {self.recette.nom}"


class ProductionIngredient(models.Model):
    """Ingrédients consommés pour une production"""

    production = models.ForeignKey(
        Production,
        on_delete=models.CASCADE,
        related_name='ingredients'
    )
    ligne = models.ForeignKey(
        ProductionLigne,
        on_delete=models.CASCADE,
        related_name='ingredients',
        null=True,
        blank=True,
        help_text="Ligne de production à laquelle cet ingrédient est attribué"
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE
    )
    quantite = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    cout_unitaire = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
        help_text="Coût unitaire au moment de la consommation"
    )
    unite = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        db_table = 'restaurant_production_ingredients'
        verbose_name = 'Ingrédient consommé'
        verbose_name_plural = 'Ingrédients consommés'
    
    def __str__(self):
        return f"{self.quantite} x {self.produit.nom}"
    
    
    
    
    
    
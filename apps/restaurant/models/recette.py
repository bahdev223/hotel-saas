# apps/restaurant/models/recette.py
import uuid
from decimal import Decimal
from django.db import models
from apps.stock.models import Produit


def generate_recette_id():
    """Génère un ID unique pour une recette"""
    return f"R{uuid.uuid4().hex[:8].upper()}"


def generate_ingredient_id():
    """Génère un ID unique pour un ingrédient"""
    return f"I{uuid.uuid4().hex[:8].upper()}"


def generate_etape_id():
    """Génère un ID unique pour une étape"""
    return f"E{uuid.uuid4().hex[:8].upper()}"


class RecetteModel(models.Model):
    """Recette culinaire du restaurant"""
    
    TYPE_RECETTE_CHOICES = [
        ('PLAT', 'Plat'),
        ('BOISSON', 'Boisson'),
        ('DESSERT', 'Dessert'),
        ('COCKTAIL', 'Cocktail'),
        ('PETIT_DEJEUNER', 'Petit-déjeuner'),
        ('ACCOMPAGNEMENT', 'Accompagnement'),
    ]
    
    UNITE_CHOICES = [
        ('kg', 'Kilogramme'),
        ('g', 'Gramme'),
        ('l', 'Litre'),
        ('ml', 'Millilitre'),
        ('piece', 'Pièce'),
        ('cuillere_cafe', 'Cuillère à café'),
        ('cuillere_soupe', 'Cuillère à soupe'),
        ('verre', 'Verre'),
        ('bouteille', 'Bouteille'),
        ('pincee', 'Pincée'),
        ('morceau', 'Morceau'),
        ('louche', 'Louche'),
        ('poignee', 'Poignée'),
        ('unite', 'Unité'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, default=generate_recette_id, editable=False)
    code = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nom = models.CharField(max_length=100)
    type_recette = models.CharField(max_length=20, choices=TYPE_RECETTE_CHOICES)
    description = models.TextField(blank=True, null=True)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    temps_preparation_minutes = models.IntegerField(default=0)
    
    rendement_quantite = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, help_text="Quantité produite par la recette (ex: 50 litres de sauce)")
    
    rendement_unite_mesure = models.ForeignKey(
        'stock.UniteMesure',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='recettes_rendement',
        help_text="Unité de rendement (remplace rendement_unite)"
    )
    produit_fini = models.ForeignKey(Produit, on_delete=models.SET_NULL, null=True, blank=True, related_name='produit_par_recettes', help_text="Produit fini obtenu après exécution de la recette")

    visible_dans_pos = models.BooleanField(default=True)
    ordre_affichage = models.IntegerField(default=0)
    image = models.ImageField(upload_to='recettes/', blank=True, null=True)
    
    actif = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'restaurant_recettes'
        verbose_name = 'Recette'
        verbose_name_plural = 'Recettes'
        ordering = ['ordre_affichage', 'nom']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"

    @property
    def rendement_unite(self):
        return self.rendement_unite_mesure.symbole if self.rendement_unite_mesure else ''
    
    @property
    def cout_ingredients(self):
        return self.cout_total_preparation({})

    def cout_total_preparation(self, produits: dict = None) -> Decimal:
        """
        Coût total des ingrédients DEDUIRE pour UNE exécution complète de la recette.
        Lève une erreur si une conversion d'unité échoue.
        """
        from apps.stock.services.conversion_unite_service import ConversionUniteService
        from decimal import Decimal

        produits = produits or {}
        total = Decimal('0')
        for ingredient in self.ingredients.all():
            if ingredient.type_ingredient == 'DEDUIRE' and ingredient.produit:
                cout_unitaire_base = produits.get(ingredient.produit.code, ingredient.produit.prix_achat)
                if not ingredient.quantite:
                    continue
                qte_en_base = ConversionUniteService.convertir(
                    quantite=ingredient.quantite,
                    unite_source=ingredient.unite_mesure,
                    unite_dest=ingredient.produit.unite_mesure,
                    produit=ingredient.produit
                )
                total += qte_en_base * Decimal(str(cout_unitaire_base))
            elif ingredient.cout_unitaire:
                if not ingredient.quantite:
                    continue
                total += Decimal(str(ingredient.quantite)) * ingredient.cout_unitaire
        return total

    def cout_unitaire_rendement(self, produits: dict = None) -> Decimal:
        """
        Coût par unité de rendement (ex: coût au litre, au kg, à la pièce).
        Si rendement_quantite est défini : total / rendement_quantite.
        Sinon : retourne le coût total (coût par exécution).
        """
        from decimal import Decimal
        total = self.cout_total_preparation(produits)
        if self.rendement_quantite and self.rendement_quantite > 0:
            return total / Decimal(str(self.rendement_quantite))
        return total

    def cout_revient(self, produits: dict = None) -> Decimal:
        """Alias rétrocompatible – délègue à cout_total_preparation."""
        return self.cout_total_preparation(produits)
    



class IngredientModel(models.Model):
    """Ingrédient d'une recette"""
    
    TYPE_INGREDIENT_CHOICES = [
        ('DEDUIRE', 'Déduire du stock'),
        ('NE_PAS_DEDUIRE', 'Ne pas déduire (charge)'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, default=generate_ingredient_id, editable=False)
    recette = models.ForeignKey(RecetteModel, on_delete=models.CASCADE, related_name='ingredients')
    
    produit = models.ForeignKey(Produit, on_delete=models.CASCADE, null=True, blank=True)
    
    type_ingredient = models.CharField(max_length=20, choices=TYPE_INGREDIENT_CHOICES, default='DEDUIRE')
    nom = models.CharField(max_length=100, blank=True, null=True)
    
    quantite = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, default=0)
    
    unite_mesure = models.ForeignKey(
        'stock.UniteMesure',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='ingredients_recette',
        help_text="Unité de mesure (remplace unite)"
    )
    cout_unitaire = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        db_table = 'restaurant_ingredients'
        verbose_name = 'Ingrédient'
        verbose_name_plural = 'Ingrédients'
    
    def __str__(self):
        if self.type_ingredient == 'DEDUIRE' and self.produit:
            if self.quantite:
                return f"{self.produit.nom} - {self.quantite} {self.unite}"
            return f"{self.produit.nom} (quantité approximative)"
        return f"{self.nom or 'Ingrédient'} - {self.quantite} {self.unite}"

    @property
    def unite(self):
        return self.unite_mesure.symbole if self.unite_mesure else ''


class EtapePreparationModel(models.Model):
    """Étape de préparation d'une recette"""
    
    id = models.CharField(max_length=50, primary_key=True, default=generate_etape_id, editable=False)
    recette = models.ForeignKey(RecetteModel, on_delete=models.CASCADE, related_name='etapes')
    ordre = models.IntegerField()
    instruction = models.TextField()
    duree_minutes = models.IntegerField(null=True, blank=True)
    
    class Meta:
        db_table = 'restaurant_etapes_preparation'
        verbose_name = 'Étape de préparation'
        verbose_name_plural = 'Étapes de préparation'
        ordering = ['ordre']
    
    def __str__(self):
        return f"{self.ordre}. {self.instruction[:50]}"
    
    
    
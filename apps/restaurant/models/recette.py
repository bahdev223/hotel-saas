# apps/restaurant/models/recette.py
import uuid
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
    rendement_unite = models.CharField(max_length=20, choices=UNITE_CHOICES, null=True, blank=True)
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
        return f"{self.nom} ({self.get_type_recette_display()})"
    
    def cout_revient(self, produits: dict) -> float:
        total = 0.0
        for ingredient in self.ingredients.all():
            if ingredient.type_ingredient == 'DEDUIRE':
                produit = produits.get(ingredient.produit_id)
                if not produit:
                    continue
                prix = ingredient.cout_unitaire or produit.prix_achat
            else:
                if not ingredient.cout_unitaire:
                    continue
                prix = ingredient.cout_unitaire
            
            if ingredient.quantite and ingredient.quantite > 0:
                quantite = float(ingredient.quantite)
            else:
                continue
            
            total += quantite * float(prix)
        return total
    
    def consommer_ingredients(self, quantite=1, entrepot=None):
        from apps.stock.services.mouvement_service import MouvementStockService

        if not entrepot:
            return

        for ingredient in self.ingredients.filter(type_ingredient='DEDUIRE'):
            if not ingredient.quantite or ingredient.quantite <= 0 or not ingredient.produit:
                continue

            quantite_necessaire = ingredient.quantite * Decimal(str(quantite))
            MouvementStockService.sortie_stock(
                produit=ingredient.produit,
                entrepot=entrepot,
                quantite=quantite_necessaire,
                utilisateur="Cuisine",
                motif='consommation',
                raison=f"Consommation recette: {self.nom}",
            )

    def verifier_disponibilite(self, quantite=1, entrepot=None):
        from apps.stock.models import StockEntrepot

        manques = []

        for ingredient in self.ingredients.filter(type_ingredient='DEDUIRE'):
            if not ingredient.quantite or ingredient.quantite <= 0 or not ingredient.produit:
                continue

            stock = StockEntrepot.objects.filter(
                entrepot=entrepot,
                produit=ingredient.produit
            ).first() if entrepot else None

            stock_qte = float(stock.quantite) if stock else 0
            besoin = float(ingredient.quantite) * quantite

            if stock_qte < besoin:
                manques.append({
                    'produit': ingredient.produit.nom,
                    'disponible': stock_qte,
                    'besoin': besoin,
                    'unite': ingredient.unite
                })

        return {
            'disponible': len(manques) == 0,
            'manques': manques
        }


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
    unite = models.CharField(max_length=20, choices=RecetteModel.UNITE_CHOICES, default='piece')
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
    
    
    
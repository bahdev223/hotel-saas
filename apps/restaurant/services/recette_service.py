# apps/restaurant/services/recette_service.py
from django.db import transaction
from decimal import Decimal
from ..models import RecetteModel, IngredientModel
from apps.stock.models import Produit, StockEntrepot


class RecetteService:
    """Service de gestion des recettes"""
    
    @staticmethod
    def calculer_cout_revient(recette, produits_dict=None):
        """Calcule le coût de revient d'une recette"""
        produits_dict = produits_dict or {}
        total = Decimal('0')
        
        for ingredient in recette.ingredients.filter(type_ingredient='DEDUIRE'):
            if ingredient.produit and ingredient.quantite:
                prix = ingredient.cout_unitaire or ingredient.produit.prix_achat
                total += ingredient.quantite * prix
        
        return total
    
    @staticmethod
    def verifier_disponibilite(recette, entrepot):
        """Vérifie si tous les ingrédients sont disponibles"""
        manques = []
        
        for ingredient in recette.ingredients.filter(type_ingredient='DEDUIRE'):
            if not ingredient.produit or not ingredient.quantite:
                continue
            
            stock = StockEntrepot.objects.filter(
                entrepot=entrepot,
                produit=ingredient.produit
            ).first()
            
            stock_qte = stock.quantite if stock else Decimal('0')
            besoin = ingredient.quantite
            
            if stock_qte < besoin:
                manques.append({
                    'produit': ingredient.produit.nom,
                    'disponible': float(stock_qte),
                    'besoin': float(besoin),
                    'unite': ingredient.unite
                })
        
        return {
            'disponible': len(manques) == 0,
            'manques': manques
        }
    
    @staticmethod
    @transaction.atomic
    def dupliquer_recette(recette, nouveau_code, nouveau_nom):
        """Duplique une recette existante"""
        nouvelle_recette = RecetteModel.objects.create(
            code=nouveau_code,
            nom=nouveau_nom,
            type_recette=recette.type_recette,
            description=recette.description,
            temps_preparation_minutes=recette.temps_preparation_minutes,
            actif=True
        )
        
        for ingredient in recette.ingredients.all():
            IngredientModel.objects.create(
                id=str(uuid.uuid4()),
                recette=nouvelle_recette,
                produit=ingredient.produit,
                type_ingredient=ingredient.type_ingredient,
                nom=ingredient.nom,
                quantite=ingredient.quantite,
                unite=ingredient.unite,
                cout_unitaire=ingredient.cout_unitaire
            )
        
        return nouvelle_recette
    
    @staticmethod
    def get_ingredients_manquants(recette, entrepot):
        """Récupère la liste des ingrédients manquants"""
        resultat = RecetteService.verifier_disponibilite(recette, entrepot)
        return resultat['manques']
    
    
    
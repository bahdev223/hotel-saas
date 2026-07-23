# apps/restaurant/services/consommation_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.stock.models import StockEntrepot, Entrepot, MouvementStock
from ..models import CommandeRestaurantModel


class ConsommationService:
    """Service de consommation des ingrédients quand une commande est servie"""
    
    @classmethod
    def get_restaurant_entrepot(cls):
        """Récupère l'entrepôt RESTAURANT"""
        entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
        if not entrepot:
            entrepot = Entrepot.objects.create(
                code='RESTAURANT',
                nom='RESTAURANT',
                type_entrepot='RESTAURANT',
                actif=True
            )
        return entrepot
    
    @classmethod
    @transaction.atomic
    def consommer_commande(cls, commande_id, utilisateur=None):
        """Consomme tous les ingrédients d'une commande"""
        commande = CommandeRestaurantModel.objects.get(id=commande_id)
        restaurant_entrepot = cls.get_restaurant_entrepot()
        resultats = []
        stock_insuffisant = []
        
        for ligne in commande.lignes.all():
            # Vérifier si déjà consommé
            if ligne.stock_consomme:
                continue
            
            # Si c'est un produit direct (pas une recette)
            if ligne.produit and not ligne.recette:
                # Consommer le produit directement
                besoin = ligne.quantite
                produit = ligne.produit
                
                stock = StockEntrepot.objects.filter(
                    entrepot=restaurant_entrepot,
                    produit=produit
                ).first()
                
                stock_disponible = stock.quantite if stock else 0
                
                if stock_disponible < besoin:
                    stock_insuffisant.append({
                        'produit': produit.nom,
                        'disponible': float(stock_disponible),
                        'besoin': float(besoins),
                        'unite': produit.unite_base
                    })
                else:
                    stock.quantite -= besoin
                    stock.save()
                    
                    MouvementStock.objects.create(
                        produit=produit,
                        type_mouvement='SORTIE',
                        quantite=besoin,
                        entrepot_source=restaurant_entrepot,
                        utilisateur=utilisateur or 'CUISINE',
                        reference=commande.id,
                        raison=f"Commande #{commande.id[:8]} - Vente directe"
                    )
                    
                    ligne.stock_consomme = True
                    ligne.date_consommation = timezone.now()
                    ligne.save()
                    
                    resultats.append({
                        'produit': produit.nom,
                        'quantite': float(besoin),
                        'statut': 'CONSOMME'
                    })
            
            # Si c'est une recette
            elif ligne.recette:
                recette = ligne.recette
                quantite = ligne.quantite
                
                # Vérifier les ingrédients
                for ingredient in recette.ingredients.filter(type_ingredient='DEDUIRE'):
                    produit = ingredient.produit
                    besoin = ingredient.quantite * quantite
                    
                    stock = StockEntrepot.objects.filter(
                        entrepot=restaurant_entrepot,
                        produit=produit
                    ).first()
                    
                    stock_disponible = stock.quantite if stock else 0
                    
                    if stock_disponible < besoin:
                        stock_insuffisant.append({
                            'produit': produit.nom,
                            'disponible': float(stock_disponible),
                            'besoin': float(besoin),
                            'unite': ingredient.unite,
                            'recette': recette.nom
                        })
                
                if stock_insuffisant:
                    raise Exception(f"Stock insuffisant: {stock_insuffisant}")
                
                # Consommer les ingrédients
                for ingredient in recette.ingredients.filter(type_ingredient='DEDUIRE'):
                    produit = ingredient.produit
                    besoin = ingredient.quantite * quantite
                    
                    stock = StockEntrepot.objects.get(
                        entrepot=restaurant_entrepot,
                        produit=produit
                    )
                    stock.quantite -= besoin
                    stock.save()
                    
                    MouvementStock.objects.create(
                        produit=produit,
                        type_mouvement='SORTIE',
                        quantite=besoin,
                        entrepot_source=restaurant_entrepot,
                        utilisateur=utilisateur or 'CUISINE',
                        reference=commande.id,
                        raison=f"Commande #{commande.id[:8]} - {recette.nom} x{quantite}"
                    )
                
                ligne.stock_consomme = True
                ligne.date_consommation = timezone.now()
                ligne.save()
                
                resultats.append({
                    'recette': recette.nom,
                    'quantite': quantite,
                    'statut': 'CONSOMME'
                })
        
        if stock_insuffisant:
            return {
                'success': False,
                'error': 'Stock insuffisant',
                'details': stock_insuffisant
            }
        
        return {
            'success': True,
            'lignes_consommees': resultats
        }
    
    @classmethod
    def verifier_stock_recette(cls, recette_id, quantite=1):
        """Vérifie si une recette peut être préparée"""
        from ..models import RecetteModel
        recette = RecetteModel.objects.get(id=recette_id)
        restaurant_entrepot = cls.get_restaurant_entrepot()
        
        manques = []
        for ingredient in recette.ingredients.filter(type_ingredient='DEDUIRE'):
            produit = ingredient.produit
            besoin = ingredient.quantite * quantite
            
            stock = StockEntrepot.objects.filter(
                entrepot=restaurant_entrepot,
                produit=produit
            ).first()
            
            stock_disponible = stock.quantite if stock else 0
            
            if stock_disponible < besoin:
                manques.append({
                    'produit': produit.nom,
                    'disponible': float(stock_disponible),
                    'besoin': float(besoin),
                    'unite': ingredient.unite,
                    'manquant': float(besoin - stock_disponible)
                })
        
        return {
            'possible': len(manques) == 0,
            'manques': manques
        }
        
        
        
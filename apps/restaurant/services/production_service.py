# apps/restaurant/services/production_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.stock.models import Produit, StockEntrepot, MouvementStock
from apps.restaurant.models import RecetteModel, IngredientModel, Production, ProductionLigne, ProductionIngredient


class ProductionService:
    """Service pour gérer la production en cuisine"""
    
    @staticmethod
    def verifier_stock_ingredients(recette, quantite=1):
        """Vérifie si les ingrédients d'une recette sont disponibles"""
        manques = []
        
        for ingredient in recette.ingredients.all():
            produit = ingredient.produit
            quantite_requise = ingredient.quantite * Decimal(str(quantite))
            
            # Vérifier le stock dans l'entrepôt RESTAURANT
            stock = StockEntrepot.objects.filter(
                entrepot__type_entrepot='RESTAURANT',
                produit=produit
            ).first()
            
            quantite_dispo = stock.quantite if stock else Decimal('0')
            
            if quantite_dispo < quantite_requise:
                manques.append({
                    'produit_id': produit.id,
                    'produit_nom': produit.nom,
                    'requis': float(quantite_requise),
                    'disponible': float(quantite_dispo),
                    'unite': produit.unite_base
                })
        
        return manques
    
    @staticmethod
    def destocker_ingredients(recette, quantite=1, entrepot=None):
        """Déstocke les ingrédients d'une recette"""
        from apps.stock.models import Entrepot
        
        if not entrepot:
            entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
        
        if not entrepot:
            raise ValueError("Entrepôt RESTAURANT non trouvé")
        
        mouvements = []
        
        for ingredient in recette.ingredients.all():
            produit = ingredient.produit
            quantite_sortie = ingredient.quantite * Decimal(str(quantite))
            
            # Récupérer le stock
            stock = StockEntrepot.objects.get(entrepot=entrepot, produit=produit)
            
            if stock.quantite < quantite_sortie:
                raise ValueError(f"Stock insuffisant pour {produit.nom}")
            
            # Créer le mouvement
            mouvement = MouvementStock.objects.create(
                produit=produit,
                type_mouvement='SORTIE',
                quantite=quantite_sortie,
                entrepot_source=entrepot,
                reference=f"PROD-{recette.nom}",
                raison=f"Production: {recette.nom}",
                utilisateur="Cuisine"
            )
            
            # Mettre à jour le stock
            stock.quantite -= quantite_sortie
            stock.save()
            
            mouvements.append(mouvement)
        
        return mouvements
    

def destocker_commande(commande):
    """Déstocke les ingrédients d'une commande"""
    from apps.stock.models import Entrepot
    
    entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    
    if not entrepot:
        return {'success': False, 'errors': ['Entrepôt restaurant non trouvé']}
    
    errors = []
    
    for ligne in commande.lignes.all():
        if ligne.menu:
            for ligne_menu in ligne.menu.lignes.all():
                if ligne_menu.recette:
                    try:
                        ProductionService.destocker_ingredients(
                            ligne_menu.recette, 
                            ligne.quantite, 
                            entrepot
                        )
                    except Exception as e:
                        errors.append(str(e))
        
        elif ligne.produit:
            try:
                produit = ligne.produit
                quantite = ligne.quantite
                
                stock = StockEntrepot.objects.get(entrepot=entrepot, produit=produit)
                
                if stock.quantite < quantite:
                    errors.append(f"Stock insuffisant pour {produit.nom}")
                    continue
                
                MouvementStock.objects.create(
                    produit=produit,
                    type_mouvement='SORTIE',
                    quantite=quantite,
                    entrepot_source=entrepot,
                    reference=f"CMD-{commande.numero}",
                    raison=f"Commande #{commande.numero}",
                    utilisateur="Cuisine"
                )
                
                stock.quantite -= quantite
                stock.save()
                
            except Exception as e:
                errors.append(str(e))
    
    if errors:
        return {'success': False, 'errors': errors}
    
    return {'success': True}


def verifier_stock_commande(commande):
    """Vérifie si tous les ingrédients d'une commande sont disponibles"""
    from apps.stock.models import Entrepot
    
    entrepot = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
    
    if not entrepot:
        return {'success': False, 'errors': ['Entrepôt restaurant non trouvé']}
    
    manques = []
    
    for ligne in commande.lignes.all():
        if ligne.menu:
            for ligne_menu in ligne.menu.lignes.all():
                if ligne_menu.recette:
                    for ingredient in ligne_menu.recette.ingredients.all():
                        quantite_requise = ingredient.quantite * ligne.quantite
                        stock = StockEntrepot.objects.filter(
                            entrepot=entrepot, 
                            produit=ingredient.produit
                        ).first()
                        quantite_dispo = stock.quantite if stock else Decimal('0')
                        
                        if quantite_dispo < quantite_requise:
                            manques.append({
                                'produit': ingredient.produit.nom,
                                'requis': float(quantite_requise),
                                'disponible': float(quantite_dispo),
                                'unite': ingredient.produit.unite_base
                            })
        
        elif ligne.produit:
            stock = StockEntrepot.objects.filter(entrepot=entrepot, produit=ligne.produit).first()
            quantite_dispo = stock.quantite if stock else Decimal('0')
            
            if quantite_dispo < ligne.quantite:
                manques.append({
                    'produit': ligne.produit.nom,
                    'requis': float(ligne.quantite),
                    'disponible': float(quantite_dispo),
                    'unite': ligne.produit.unite_base
                })
    
    if manques:
        return {'success': False, 'errors': manques}
    
    return {'success': True}


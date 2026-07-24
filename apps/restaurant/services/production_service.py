# apps/restaurant/services/production_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.stock.models import Produit, StockEntrepot
from apps.restaurant.models import RecetteModel, IngredientModel, Production, ProductionLigne, ProductionIngredient


class ProductionService:
    """Service pour gérer la production en cuisine"""

    @staticmethod
    def verifier_stock_ingredients(recette, quantite=1, entrepot=None):
        if not entrepot:
            raise ValueError("entrepot requis")

        manques = []

        for ingredient in recette.ingredients.filter(produit__isnull=False):
            produit = ingredient.produit
            quantite_requise = ingredient.quantite * Decimal(str(quantite)) if ingredient.quantite else Decimal('0')

            stock = StockEntrepot.objects.filter(
                entrepot=entrepot,
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
        from apps.stock.services.mouvement_service import MouvementStockService

        if not entrepot:
            raise ValueError("entrepot requis")

        for ingredient in recette.ingredients.filter(produit__isnull=False):
            if not ingredient.quantite:
                continue

            quantite_sortie = ingredient.quantite * Decimal(str(quantite))

            MouvementStockService.sortie_stock(
                produit=ingredient.produit,
                entrepot=entrepot,
                quantite=quantite_sortie,
                utilisateur="Cuisine",
                motif='consommation',
                raison=f"Production: {recette.nom}",
            )


def destocker_commande(commande, entrepot=None):
    from apps.stock.services.mouvement_service import MouvementStockService

    if not entrepot:
        return {'success': False, 'errors': ['Entrepôt requis']}

    errors = []

    for ligne in commande.lignes.all():
        try:
            if ligne.recette:
                ProductionService.destocker_ingredients(
                    ligne.recette,
                    ligne.quantite,
                    entrepot
                )

            elif ligne.menu:
                for ligne_menu in ligne.menu.lignes.filter(type_ligne='FIXE'):
                    if ligne_menu.recette:
                        ProductionService.destocker_ingredients(
                            ligne_menu.recette,
                            ligne.quantite * ligne_menu.quantite,
                            entrepot
                        )

            elif ligne.produit:
                MouvementStockService.sortie_stock(
                    produit=ligne.produit,
                    entrepot=entrepot,
                    quantite=ligne.quantite,
                    utilisateur="Cuisine",
                    motif='vente',
                    raison=f"Commande #{commande.numero}",
                )

        except Exception as e:
            errors.append(str(e))

    if errors:
        return {'success': False, 'errors': errors}

    return {'success': True}


def verifier_stock_commande(commande, entrepot=None):
    if not entrepot:
        return {'success': False, 'errors': ['Entrepôt requis']}

    with_decimals = Decimal(str(0))
    manques = []

    for ligne in commande.lignes.all():
        if ligne.recette:
            for ingredient in ligne.recette.ingredients.filter(produit__isnull=False):
                if not ingredient.quantite:
                    continue
                quantite_requise = ingredient.quantite * ligne.quantite
                stock = StockEntrepot.objects.filter(
                    entrepot=entrepot,
                    produit=ingredient.produit
                ).first()
                quantite_dispo = stock.quantite if stock else with_decimals

                if quantite_dispo < quantite_requise:
                    manques.append({
                        'produit': ingredient.produit.nom,
                        'requis': float(quantite_requise),
                        'disponible': float(quantite_dispo),
                        'unite': ingredient.produit.unite_base
                    })

        elif ligne.menu:
            for ligne_menu in ligne.menu.lignes.filter(type_ligne='FIXE'):
                if not ligne_menu.recette:
                    continue
                for ingredient in ligne_menu.recette.ingredients.filter(produit__isnull=False):
                    if not ingredient.quantite:
                        continue
                    quantite_requise = ingredient.quantite * ligne.quantite * ligne_menu.quantite
                    stock = StockEntrepot.objects.filter(
                        entrepot=entrepot,
                        produit=ingredient.produit
                    ).first()
                    quantite_dispo = stock.quantite if stock else with_decimals

                    if quantite_dispo < quantite_requise:
                        manques.append({
                            'produit': ingredient.produit.nom,
                            'requis': float(quantite_requise),
                            'disponible': float(quantite_dispo),
                            'unite': ingredient.produit.unite_base
                        })

        elif ligne.produit:
            stock = StockEntrepot.objects.filter(entrepot=entrepot, produit=ligne.produit).first()
            quantite_dispo = stock.quantite if stock else with_decimals

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

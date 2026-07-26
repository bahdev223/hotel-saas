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
        from apps.stock.services.conversion_unite_service import ConversionUniteService

        if not entrepot:
            raise ValueError("entrepot requis")

        manques = []

        for ingredient in recette.ingredients.filter(produit__isnull=False):
            produit = ingredient.produit
            qte_base = ConversionUniteService.convertir(
                quantite=ingredient.quantite,
                unite_source=ingredient.unite_mesure,
                unite_dest=ingredient.produit.unite_mesure,
                produit=ingredient.produit
            )

            quantite_requise = qte_base * Decimal(str(quantite)) if qte_base else Decimal('0')

            stock = StockEntrepot.objects.filter(
                entrepot=entrepot,
                produit=produit
            ).first()

            quantite_dispo = stock.quantite if stock else Decimal('0')

            if quantite_dispo < quantite_requise:
                manques.append({
                    'produit_id': produit.id,
                    'produit_nom': produit.nom,
                    'requis': quantite_requise,
                    'disponible': quantite_dispo,
                    'unite': produit.unite_base
                })

        return manques

    @staticmethod
    def destocker_ingredients(recette, quantite=1, entrepot=None, source_operation=None):
        from apps.stock.services.mouvement_service import MouvementStockService
        from apps.stock.services.conversion_unite_service import ConversionUniteService

        if not entrepot:
            raise ValueError("entrepot requis")

        for ingredient in recette.ingredients.filter(produit__isnull=False):
            if not ingredient.quantite:
                continue

            qte_base = ConversionUniteService.convertir(
                quantite=ingredient.quantite,
                unite_source=ingredient.unite_mesure,
                unite_dest=ingredient.produit.unite_mesure,
                produit=ingredient.produit
            )

            quantite_sortie = qte_base * Decimal(str(quantite))

            MouvementStockService.sortie_stock(
                produit=ingredient.produit,
                entrepot=entrepot,
                quantite=quantite_sortie,
                utilisateur="Cuisine",
                motif='consommation',
                raison=f"Production: {recette.nom}",
                source_operation=source_operation,
            )


    @staticmethod
    def verifier_stock_production(production):
        """Vérifie si tous les ingrédients sont disponibles pour une production."""
        from apps.stock.services.conversion_unite_service import ConversionUniteService
        manques = []

        for ligne in production.lignes.select_related('recette').all():
            if not ligne.recette:
                manques.append(f"Ligne #{ligne.id}: aucune recette associée")
                continue

            for ingredient in ligne.recette.ingredients.filter(
                type_ingredient='DEDUIRE',
                produit__isnull=False
            ):
                if not ingredient.quantite:
                    continue

                qte_base = ConversionUniteService.convertir(
                    quantite=ingredient.quantite,
                    unite_source=ingredient.unite_mesure,
                    unite_dest=ingredient.produit.unite_mesure,
                    produit=ingredient.produit
                )
                quantite_necessaire = qte_base * ligne.quantite
                stock = StockEntrepot.objects.filter(
                    entrepot=production.entrepot_source,
                    produit=ingredient.produit
                ).first()

                stock_qte = stock.quantite if stock else Decimal('0')

                if stock_qte < quantite_necessaire:
                    manques.append(
                        f"{ingredient.produit.nom}: besoin {quantite_necessaire} {ingredient.unite}, "
                        f"disponible {stock_qte}"
                    )

        return {'disponible': len(manques) == 0, 'manques': manques}

    @staticmethod
    @transaction.atomic
    def valider_production(production, employe):
        """Valide la production : sortie ingrédients + entrée produit fini."""
        from apps.stock.services.mouvement_service import MouvementStockService
        from apps.stock.enums.sources import SourceOperationType
        from apps.stock.services.conversion_unite_service import ConversionUniteService
        from apps.stock.models import SourceOperation

        if production.statut == 'VALIDE':
            raise ValueError("Cette production a déjà été validée")

        if not production.entrepot_source:
            raise ValueError("Entrepôt source non défini")
        if not production.entrepot_dest:
            raise ValueError("Entrepôt destination non défini")

        # Vérifier le stock
        verification = ProductionService.verifier_stock_production(production)
        if not verification['disponible']:
            raise ValueError(f"Stock insuffisant: {', '.join(verification['manques'])}")

        # Source unique partagée pour tous les mouvements de cette production
        source_op = SourceOperation.objects.create(
            type_source=SourceOperationType.PRODUCTION,
            reference=f"PRD-{production.numero}",
            notes=f"Production #{production.numero}"
        )

        # Appliquer les modifications
        for ligne in production.lignes.select_related('recette', 'recette__produit_fini').all():
            if not ligne.recette:
                continue

            # Sortie des ingrédients
            for ingredient in ligne.recette.ingredients.filter(
                type_ingredient='DEDUIRE',
                produit__isnull=False
            ):
                if not ingredient.quantite:
                    continue

                qte_base = ConversionUniteService.convertir(
                    quantite=ingredient.quantite,
                    unite_source=ingredient.unite_mesure,
                    unite_dest=ingredient.produit.unite_mesure,
                    produit=ingredient.produit
                )
                quantite_necessaire = qte_base * ligne.quantite

                MouvementStockService.sortie_stock(
                    produit=ingredient.produit,
                    entrepot=production.entrepot_source,
                    quantite=quantite_necessaire,
                    utilisateur=str(employe) if employe else "Cuisine",
                    motif=SourceOperationType.PRODUCTION,
                    raison=f"Production #{production.numero}: {ligne.recette.nom}",
                    source_operation=source_op,
                )

                ProductionIngredient.objects.create(
                    production=production,
                    produit=ingredient.produit,
                    quantite=quantite_necessaire,
                    unite=ingredient.unite
                )

            # Entrée du produit fini dans l'entrepôt destination
            if ligne.recette.produit_fini:
                quantite_produite = ligne.quantite
                if ligne.recette.rendement_quantite:
                    quantite_produite = quantite_produite * ligne.recette.rendement_quantite

                MouvementStockService.entree_stock(
                    produit=ligne.recette.produit_fini,
                    entrepot=production.entrepot_dest,
                    quantite=quantite_produite,
                    utilisateur=str(employe) if employe else "Cuisine",
                    motif=SourceOperationType.PRODUCTION,
                    raison=f"Production #{production.numero}: {ligne.recette.nom}",
                    source_operation=source_op,
                )

        production.statut = 'VALIDE'
        production.valide_par = employe
        production.save()

        return True

    @staticmethod
    @transaction.atomic
    def annuler_production(production):
        """Annule la production (si non validée)"""
        if production.statut == 'VALIDE':
            raise ValueError("Impossible d'annuler une production validée")
        
        production.statut = 'ANNULE'
        production.save()


def destocker_commande(commande, entrepot=None, source_operation=None):
    from apps.stock.services.mouvement_service import MouvementStockService
    from decimal import Decimal

    if not entrepot:
        return {'success': False, 'errors': ['Entrepôt requis']}

    errors = []

    for ligne in commande.lignes.all():
        try:
            if ligne.recette:
                ProductionService.destocker_ingredients(
                    ligne.recette,
                    ligne.quantite,
                    entrepot,
                    source_operation=source_operation,
                )

            elif ligne.menu:
                for ligne_menu in ligne.menu.lignes.filter(type_ligne='FIXE'):
                    if ligne_menu.recette:
                        ProductionService.destocker_ingredients(
                            ligne_menu.recette,
                            ligne.quantite * ligne_menu.quantite,
                            entrepot,
                            source_operation=source_operation,
                        )

            elif ligne.produit:
                MouvementStockService.sortie_stock(
                    produit=ligne.produit,
                    entrepot=entrepot,
                    quantite=ligne.quantite,
                    utilisateur="Cuisine",
                    motif='vente',
                    raison=f"Commande #{commande.numero}",
                    source_operation=source_operation,
                )

        except Exception as e:
            errors.append(str(e))

    if errors:
        return {'success': False, 'errors': errors}

    return {'success': True}


def verifier_stock_commande(commande, entrepot=None):
    from apps.stock.services.conversion_unite_service import ConversionUniteService
    from decimal import Decimal

    if not entrepot:
        return {'success': False, 'errors': ['Entrepôt requis']}

    manques = []

    for ligne in commande.lignes.all():
        if ligne.recette:
            for ingredient in ligne.recette.ingredients.filter(produit__isnull=False):
                if not ingredient.quantite:
                    continue
                qte_base = ConversionUniteService.convertir(
                    quantite=ingredient.quantite,
                    unite_source=ingredient.unite_mesure,
                    unite_dest=ingredient.produit.unite_mesure,
                    produit=ingredient.produit
                )
                quantite_requise = qte_base * ligne.quantite
                stock = StockEntrepot.objects.filter(
                    entrepot=entrepot,
                    produit=ingredient.produit
                ).first()
                quantite_dispo = stock.quantite if stock else Decimal('0')

                if quantite_dispo < quantite_requise:
                    manques.append({
                        'produit': ingredient.produit.nom,
                        'requis': quantite_requise,
                        'disponible': quantite_dispo,
                        'unite': ingredient.produit.unite_base
                    })

        elif ligne.menu:
            for ligne_menu in ligne.menu.lignes.filter(type_ligne='FIXE'):
                if not ligne_menu.recette:
                    continue
                for ingredient in ligne_menu.recette.ingredients.filter(produit__isnull=False):
                    if not ingredient.quantite:
                        continue
                    qte_base = ConversionUniteService.convertir(
                        quantite=ingredient.quantite,
                        unite_source=ingredient.unite_mesure,
                        unite_dest=ingredient.produit.unite_mesure,
                        produit=ingredient.produit
                    )
                    quantite_requise = qte_base * ligne.quantite * ligne_menu.quantite
                    stock = StockEntrepot.objects.filter(
                        entrepot=entrepot,
                        produit=ingredient.produit
                    ).first()
                    quantite_dispo = stock.quantite if stock else Decimal('0')

                    if quantite_dispo < quantite_requise:
                        manques.append({
                            'produit': ingredient.produit.nom,
                            'requis': quantite_requise,
                            'disponible': quantite_dispo,
                            'unite': ingredient.produit.unite_base
                        })

        elif ligne.produit:
            stock = StockEntrepot.objects.filter(entrepot=entrepot, produit=ligne.produit).first()
            quantite_dispo = stock.quantite if stock else Decimal('0')

            if quantite_dispo < ligne.quantite:
                manques.append({
                    'produit': ligne.produit.nom,
                    'requis': ligne.quantite,
                    'disponible': quantite_dispo,
                    'unite': ligne.produit.unite_base
                })

    if manques:
        return {'success': False, 'errors': manques}

    return {'success': True}

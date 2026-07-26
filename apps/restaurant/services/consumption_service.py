from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from apps.stock.models import StockEntrepot, MouvementStock, SourceOperation
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.services.conversion_unite_service import ConversionUniteService
from apps.stock.enums.sources import SourceOperationType


class RestaurantConsumptionService:
    """
    Service centralisé de consommation des stocks pour le restaurant.
    Point d'entrée unique pour tout déstockage de commandes/recettes.
    Garantit : atomicité, idempotence, source_operation partagée.
    """

    @staticmethod
    @transaction.atomic
    def consommer_commande(commande, entrepot=None, utilisateur="Cuisine"):
        """
        Consomme tous les ingrédients d'une commande POS (recettes, menus, produits).
        Atomique : tout ou rien.
        Idempotent : une commande déjà consommée ne déclenche rien.
        """
        if not entrepot:
            raise ValueError("Entrepôt requis pour la consommation")

        # Idempotence : vérifier si déjà consommée
        if MouvementStock.objects.filter(
            reference=commande.numero,
            motif='consommation'
        ).exists():
            return {'success': True, 'idempotent': True}

        # Source unique partagée pour tous les mouvements de cette commande
        source_op = SourceOperation.objects.create(
            type_source=SourceOperationType.CONSOMMATION,
            reference=commande.numero,
            notes=f"Consommation commande #{commande.numero}"
        )

        errors = []

        for ligne in commande.lignes.all():
            try:
                if ligne.recette:
                    RestaurantConsumptionService._consommer_recette(
                        recette=ligne.recette,
                        quantite=ligne.quantite,
                        entrepot=entrepot,
                        source_operation=source_op,
                        utilisateur=utilisateur,
                        reference=commande.numero,
                        raison=f"Commande #{commande.numero}: {ligne.recette.nom}",
                    )

                elif ligne.menu:
                    for ligne_menu in ligne.menu.lignes.filter(type_ligne='FIXE'):
                        if ligne_menu.recette:
                            RestaurantConsumptionService._consommer_recette(
                                recette=ligne_menu.recette,
                                quantite=ligne.quantite * ligne_menu.quantite,
                                entrepot=entrepot,
                                source_operation=source_op,
                                utilisateur=utilisateur,
                                reference=commande.numero,
                                raison=f"Commande #{commande.numero}: {ligne_menu.recette.nom}",
                            )

                elif ligne.produit:
                    MouvementStockService.sortie_stock(
                        produit=ligne.produit,
                        entrepot=entrepot,
                        quantite=ligne.quantite,
                        utilisateur=utilisateur,
                        motif='consommation',
                        reference=commande.numero,
                        raison=f"Commande #{commande.numero}: {ligne.produit.nom}",
                        source_operation=source_op,
                    )

            except Exception as e:
                errors.append(str(e))

        if errors:
            raise ValidationError(f"Erreurs de consommation: {'; '.join(errors)}")

        return {'success': True, 'idempotent': False}

    @staticmethod
    @transaction.atomic
    def consommer_recette(recette, quantite=1, entrepot=None, utilisateur="Cuisine",
                          reference="", raison=""):
        """
        Consomme les ingrédients DEDUIRE d'une recette.
        """
        if not entrepot:
            raise ValueError("Entrepôt requis")

        source_op = SourceOperation.objects.create(
            type_source=SourceOperationType.CONSOMMATION,
            reference=reference or f"RECETTE-{recette.code or recette.id}",
            notes=raison or f"Production: {recette.nom}"
        )

        RestaurantConsumptionService._consommer_recette(
            recette=recette,
            quantite=quantite,
            entrepot=entrepot,
            source_operation=source_op,
            utilisateur=utilisateur,
            reference=reference,
            raison=raison or f"Production: {recette.nom}",
        )

    @staticmethod
    def _consommer_recette(recette, quantite, entrepot, source_operation=None,
                           utilisateur="Cuisine", reference="", raison=""):
        """Consomme les ingrédients individuels d'une recette via MouvementStockService."""
        for ingredient in recette.ingredients.filter(
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

            quantite_sortie = qte_base * Decimal(str(quantite))

            MouvementStockService.sortie_stock(
                produit=ingredient.produit,
                entrepot=entrepot,
                quantite=quantite_sortie,
                utilisateur=utilisateur,
                motif='consommation',
                reference=reference,
                raison=raison or f"Production: {recette.nom}",
                source_operation=source_operation,
            )

    @staticmethod
    def verifier_disponibilite_commande(commande, entrepot=None):
        """
        Vérifie si tous les ingrédients sont disponibles pour une commande.
        Retourne {'disponible': bool, 'manques': [...]}
        """
        if not entrepot:
            return {'disponible': False, 'manques': ['Entrepôt requis']}

        manques = []

        for ligne in commande.lignes.all():
            if ligne.recette:
                manques += RestaurantConsumptionService._verifier_recette(
                    recette=ligne.recette,
                    quantite=ligne.quantite,
                    entrepot=entrepot,
                )

            elif ligne.menu:
                for ligne_menu in ligne.menu.lignes.filter(type_ligne='FIXE'):
                    if ligne_menu.recette:
                        manques += RestaurantConsumptionService._verifier_recette(
                            recette=ligne_menu.recette,
                            quantite=ligne.quantite * ligne_menu.quantite,
                            entrepot=entrepot,
                        )

            elif ligne.produit:
                stock = StockEntrepot.objects.filter(
                    entrepot=entrepot,
                    produit=ligne.produit
                ).first()
                quantite_dispo = stock.quantite if stock else Decimal('0')

                if quantite_dispo < ligne.quantite:
                    manques.append({
                        'produit': ligne.produit.nom,
                        'requis': ligne.quantite,
                        'disponible': quantite_dispo,
                        'unite': ligne.produit.unite_base
                    })

        return {
            'disponible': len(manques) == 0,
            'manques': manques
        }

    @staticmethod
    def _verifier_recette(recette, quantite, entrepot):
        """Vérifie la disponibilité des ingrédients d'une recette."""
        manques = []

        for ingredient in recette.ingredients.filter(
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

            quantite_requise = qte_base * Decimal(str(quantite))

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

        return manques

# apps/stock/services/mouvement_service.py
from decimal import Decimal
from django.db import transaction
from ..models import StockEntrepot
from .stock_compta_service import StockComptaService


class MouvementStockService:
    """Service pour gerer les mouvements de stock avec ecriture comptable
    Seul point d'entrée autorisé pour les mutations de StockEntrepot.quantite."""

    @staticmethod
    @transaction.atomic
    def entree_stock(produit, entrepot, quantite, utilisateur,
                     motif='achat', valeur_unitaire=0,
                     reference=None, raison="", unite_texte='',
                     entrepot_source=None):
        quantite = Decimal(str(quantite))
        valeur_unitaire = Decimal(str(valeur_unitaire))
        try:
            stock = StockEntrepot.objects.select_for_update().get(entrepot=entrepot, produit=produit)
        except StockEntrepot.DoesNotExist:
            stock = StockEntrepot.objects.create(entrepot=entrepot, produit=produit, quantite=0)
            stock = StockEntrepot.objects.select_for_update().get(pk=stock.pk)
        ancienne_quantite = stock.quantite
        stock.quantite += quantite
        if valeur_unitaire > 0 and stock.quantite > 0:
            ancienne_valeur = Decimal(str(ancienne_quantite)) * Decimal(str(stock.prix_achat or 0))
            nouvelle_valeur = quantite * valeur_unitaire
            stock.prix_achat = (ancienne_valeur + nouvelle_valeur) / stock.quantite
        stock.save()

        return StockComptaService.enregistrer_mouvement(
            produit=produit, type_mouvement='ENTREE', motif=motif,
            quantite=quantite, valeur_unitaire=valeur_unitaire,
            entrepot_dest=entrepot, entrepot_source=entrepot_source,
            reference=reference,
            raison=raison or "Entree de stock",
            utilisateur=utilisateur if isinstance(utilisateur, str) else utilisateur.username,
            unite_texte=unite_texte,
        )

    @staticmethod
    @transaction.atomic
    def sortie_stock(produit, entrepot, quantite, utilisateur,
                     motif='vente', valeur_unitaire=0,
                     reference=None, raison="", unite_texte='',
                     entrepot_dest=None):
        quantite = Decimal(str(quantite))
        valeur_unitaire = Decimal(str(valeur_unitaire))
        try:
            stock = StockEntrepot.objects.select_for_update().get(entrepot=entrepot, produit=produit)
        except StockEntrepot.DoesNotExist:
            raise ValueError(f"Stock introuvable pour {produit.nom} dans {entrepot.nom}")
        if stock.quantite < quantite:
            raise ValueError(f"Stock insuffisant pour {produit.nom}")
        stock.quantite -= quantite
        stock.save()

        return StockComptaService.enregistrer_mouvement(
            produit=produit, type_mouvement='SORTIE', motif=motif,
            quantite=quantite, valeur_unitaire=valeur_unitaire,
            entrepot_source=entrepot, entrepot_dest=entrepot_dest,
            reference=reference,
            raison=raison or "Sortie de stock",
            utilisateur=utilisateur if isinstance(utilisateur, str) else utilisateur.username,
            unite_texte=unite_texte,
        )

    @staticmethod
    @transaction.atomic
    def initialiser_stock(produit, entrepot, quantite, utilisateur,
                          valeur_unitaire=0, reference=None, raison="", unite_texte=''):
        quantite = Decimal(str(quantite))
        valeur_unitaire = Decimal(str(valeur_unitaire))
        try:
            stock = StockEntrepot.objects.select_for_update().get(entrepot=entrepot, produit=produit)
        except StockEntrepot.DoesNotExist:
            stock = StockEntrepot.objects.create(entrepot=entrepot, produit=produit, quantite=0)
            stock = StockEntrepot.objects.select_for_update().get(pk=stock.pk)
        stock.quantite += quantite
        stock.save()

        return StockComptaService.enregistrer_mouvement(
            produit=produit, type_mouvement='INITIALISATION', motif='stock_initial',
            quantite=quantite, valeur_unitaire=valeur_unitaire,
            entrepot_dest=entrepot, reference=reference,
            raison=raison or "Stock initial",
            utilisateur=utilisateur if isinstance(utilisateur, str) else utilisateur.username,
            unite_texte=unite_texte,
        )

    @staticmethod
    @transaction.atomic
    def ajuster_stock(produit, entrepot, nouvelle_quantite, utilisateur,
                      motif='inventaire', raison=""):
        stock = StockEntrepot.objects.select_for_update().get(entrepot=entrepot, produit=produit)
        diff = Decimal(str(nouvelle_quantite)) - stock.quantite
        if diff > 0:
            return MouvementStockService.entree_stock(
                produit, entrepot, diff, utilisateur,
                motif=motif, raison=f"Ajustement: {raison}"
            )
        elif diff < 0:
            return MouvementStockService.sortie_stock(
                produit, entrepot, abs(diff), utilisateur,
                motif=motif, raison=f"Ajustement: {raison}"
            )
        return None

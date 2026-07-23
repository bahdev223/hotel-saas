# apps/stock/services/stock_service.py
from decimal import Decimal
from django.db import transaction
from ..models import Produit, Lot, Entrepot
from .mouvement_service import MouvementStockService


class StockService:
    """Service de gestion du stock — délègue les mutations à MouvementStockService"""

    @classmethod
    @transaction.atomic
    def entree_stock(cls, produit_id, quantite, utilisateur, entrepot_id,
                     reference=None, prix_achat=None, fournisseur=None,
                     lot_numero=None, date_peremption=None):
        produit = Produit.objects.get(id=produit_id)
        entrepot = Entrepot.objects.get(id=entrepot_id)
        quantite = Decimal(str(quantite))

        if prix_achat:
            Produit.objects.filter(id=produit_id).update(prix_achat=prix_achat)

        lot = None
        if lot_numero:
            lot = Lot.objects.create(
                produit=produit, numero=lot_numero, quantite=quantite,
                quantite_restante=quantite, date_peremption=date_peremption,
                fournisseur=fournisseur, prix_achat=prix_achat
            )

        mouvement = MouvementStockService.entree_stock(
            produit=produit, entrepot=entrepot,
            quantite=quantite, utilisateur=utilisateur,
            motif='achat', valeur_unitaire=float(prix_achat or 0),
            reference=reference,
            raison=f"Achat - Fournisseur: {fournisseur or 'N/A'}"
        )
        return mouvement, lot

    @classmethod
    @transaction.atomic
    def sortie_stock(cls, produit_id, quantite, utilisateur, entrepot_source_id,
                     motif, reference=None, raison=None):
        produit = Produit.objects.get(id=produit_id)
        entrepot = Entrepot.objects.get(id=entrepot_source_id)
        quantite = Decimal(str(quantite))

        return MouvementStockService.sortie_stock(
            produit=produit, entrepot=entrepot,
            quantite=quantite, utilisateur=utilisateur,
            motif=motif, valeur_unitaire=float(produit.prix_achat or 0),
            reference=reference, raison=raison or f"Sortie {motif}"
        )

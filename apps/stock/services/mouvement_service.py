# apps/stock/services/mouvement_service.py
import logging
from decimal import Decimal
from django.db import transaction
from django.core.exceptions import ValidationError
from ..models import StockEntrepot, MouvementStock, JournalStock, SourceOperation
from ..enums.mouvements import TypeMouvement
from ..enums.sources import SourceOperationType
from .stock_compta_service import StockComptaService
from .valorisation_stock_service import ValorisationStockService
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

class MouvementStockService:
    """Service pour gerer les mouvements de stock avec ecriture comptable
    Seul point d'entrée autorisé pour les mutations de StockEntrepot.quantite."""

    @staticmethod
    @transaction.atomic
    def entree_stock(produit, entrepot, quantite, utilisateur,
                     motif=SourceOperationType.ACHAT, valeur_unitaire=0,
                     reference=None, raison="", unite_texte='',
                     entrepot_source=None, source_operation=None,
                     type_mouvement_override=None,
                     lot_numero=None, date_peremption=None, fournisseur_id=None):
        quantite = Decimal(str(quantite))
        valeur_unitaire = Decimal(str(valeur_unitaire))
        
        if quantite <= 0:
            raise ValidationError("La quantité doit être positive.")
            
        try:
            stock = StockEntrepot.objects.select_for_update().get(entrepot=entrepot, produit=produit)
        except StockEntrepot.DoesNotExist:
            stock = StockEntrepot.objects.create(entrepot=entrepot, produit=produit, quantite=0)
            stock = StockEntrepot.objects.select_for_update().get(pk=stock.pk)
            
        stock_avant = stock.quantite
        stock.quantite += quantite
        
        # Mettre à jour le prix d'achat du stock (nouveau CUMP)
        if valeur_unitaire > 0:
            stock.prix_achat = ValorisationStockService.calculer_cump_apres_entree(
                stock=stock,
                stock_avant=stock_avant,
                quantite_entree=quantite,
                cout_entree=valeur_unitaire
            )
            
        stock.save(update_fields=['quantite', 'prix_achat'])

        if not source_operation:
            source_operation = SourceOperation.objects.create(
                type_source=motif,
                reference=reference or f"ENTREE-{produit.id}-{entrepot.id}",
                notes=raison
            )

        utilisateur_username = utilisateur if isinstance(utilisateur, str) else getattr(utilisateur, 'username', 'system')
        utilisateur_obj = utilisateur if not isinstance(utilisateur, str) and isinstance(utilisateur, User) else None

        type_mouv = type_mouvement_override or TypeMouvement.ENTREE

        mouvement = MouvementStock.objects.create(
            produit=produit,
            entrepot_dest=entrepot,
            entrepot_source=entrepot_source,
            type_mouvement=type_mouv,
            motif=motif,
            quantite=quantite,
            valeur_unitaire=valeur_unitaire,
            reference=reference,
            raison=raison or "Entree de stock",
            utilisateur=utilisateur_username,
            unite_texte=unite_texte,
            source_operation=source_operation
        )

        JournalStock.objects.create(
            mouvement=mouvement,
            produit=produit,
            entrepot=entrepot,
            stock_avant=stock_avant,
            quantite_mouvement=quantite,
            stock_apres=stock.quantite,
            cout_unitaire=valeur_unitaire,
            valeur_mouvement=quantite * valeur_unitaire,
            effectue_par=utilisateur_username,
            effectue_par_user=utilisateur_obj
        )

        # Appel au module compta
        try:
            ecriture = StockComptaService.enregistrer_ecriture(mouvement)
        except Exception as e:
            logger.exception(
                "Échec de comptabilisation du mouvement %s (entrée): %s",
                mouvement.pk, e
            )
            
        # Gestion de lot
        if lot_numero:
            from .lot_allocation_service import LotAllocationService
            LotAllocationService.entree_lot(
                mouvement=mouvement,
                lot_numero=lot_numero,
                quantite=quantite,
                date_peremption=date_peremption,
                fournisseur_id=fournisseur_id
            )
            
        return mouvement

    @staticmethod
    @transaction.atomic
    def sortie_stock(produit, entrepot, quantite, utilisateur,
                     motif=SourceOperationType.VENTE, valeur_unitaire=None,
                     reference=None, raison="", unite_texte='',
                     entrepot_dest=None, source_operation=None,
                     type_mouvement_override=None):
        quantite = Decimal(str(quantite))
        
        if quantite <= 0:
            raise ValidationError("La quantité doit être positive.")
            
        try:
            stock = StockEntrepot.objects.select_for_update().get(entrepot=entrepot, produit=produit)
        except StockEntrepot.DoesNotExist:
            raise ValidationError(f"Stock introuvable pour {produit.nom} dans {entrepot.nom}")
            
        if stock.quantite < quantite:
            raise ValidationError(f"Stock insuffisant pour {produit.nom}")
            
        stock_avant = stock.quantite
        
        # Valorisation de la sortie (CUMP par defaut)
        if valeur_unitaire is None:
            cout_unitaire = ValorisationStockService.get_cout_sortie(
                produit=produit,
                entrepot=entrepot,
                quantite=quantite
            )
        else:
            cout_unitaire = Decimal(str(valeur_unitaire))
            
        stock.quantite -= quantite
        stock.save(update_fields=['quantite'])

        if not source_operation:
            source_operation = SourceOperation.objects.create(
                type_source=motif,
                reference=reference or f"SORTIE-{produit.id}-{entrepot.id}",
                notes=raison
            )

        utilisateur_username = utilisateur if isinstance(utilisateur, str) else getattr(utilisateur, 'username', 'system')
        utilisateur_obj = utilisateur if not isinstance(utilisateur, str) and isinstance(utilisateur, User) else None

        type_mouv = type_mouvement_override or TypeMouvement.SORTIE

        mouvement = MouvementStock.objects.create(
            produit=produit,
            entrepot_source=entrepot,
            entrepot_dest=entrepot_dest,
            type_mouvement=type_mouv,
            motif=motif,
            quantite=quantite,
            valeur_unitaire=cout_unitaire,
            reference=reference,
            raison=raison or "Sortie de stock",
            utilisateur=utilisateur_username,
            unite_texte=unite_texte,
            source_operation=source_operation
        )

        JournalStock.objects.create(
            mouvement=mouvement,
            produit=produit,
            entrepot=entrepot,
            stock_avant=stock_avant,
            quantite_mouvement=-quantite,
            stock_apres=stock.quantite,
            cout_unitaire=cout_unitaire,
            valeur_mouvement=quantite * cout_unitaire,
            effectue_par=utilisateur_username,
            effectue_par_user=utilisateur_obj
        )

        # Appel au module compta
        try:
            ecriture = StockComptaService.enregistrer_ecriture(mouvement)
        except Exception as e:
            logger.exception(
                "Échec de comptabilisation du mouvement %s (sortie): %s",
                mouvement.pk, e
            )

        # Gestion des lots (FEFO) si le produit a des lots dans cet entrepôt
        from ..models import StockLotEntrepot
        from .lot_allocation_service import LotAllocationService
        if StockLotEntrepot.objects.filter(lot__produit=produit, entrepot=entrepot, quantite__gt=0).exists():
            LotAllocationService.allouer_lots_fefo(mouvement, quantite)

        return mouvement

    @staticmethod
    @transaction.atomic
    def initialiser_stock(produit, entrepot, quantite, utilisateur,
                          valeur_unitaire=0, reference=None, raison="", unite_texte=''):
        return MouvementStockService.entree_stock(
            produit=produit, entrepot=entrepot, quantite=quantite,
            utilisateur=utilisateur, motif=SourceOperationType.INITIALISATION,
            valeur_unitaire=valeur_unitaire, reference=reference,
            raison=raison or "Stock initial", unite_texte=unite_texte
        )

    @staticmethod
    @transaction.atomic
    def ajuster_stock(produit, entrepot, nouvelle_quantite, utilisateur,
                      motif=SourceOperationType.INVENTAIRE, raison=""):
        stock = StockEntrepot.objects.select_for_update().get(entrepot=entrepot, produit=produit)
        diff = Decimal(str(nouvelle_quantite)) - stock.quantite
        if diff > 0:
            return MouvementStockService.entree_stock(
                produit, entrepot, diff, utilisateur,
                motif=motif, raison=f"Ajustement: {raison}",
                type_mouvement_override=TypeMouvement.AJUSTEMENT_POSITIF
            )
        elif diff < 0:
            return MouvementStockService.sortie_stock(
                produit, entrepot, abs(diff), utilisateur,
                motif=motif, raison=f"Ajustement: {raison}",
                type_mouvement_override=TypeMouvement.AJUSTEMENT_NEGATIF
            )
        return None

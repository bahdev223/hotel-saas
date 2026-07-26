# apps/stock/services/transfert_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from ..models import Produit, Entrepot
from .mouvement_service import MouvementStockService
from .conversion_unite_service import ConversionUniteService
from ..enums.mouvements import TypeMouvement
from ..enums.sources import SourceOperationType
from django.core.exceptions import ValidationError

class TransfertService:
    """Service de gestion des transferts entre entrepôts"""
    
    @classmethod
    @transaction.atomic
    def transfert_entre_entrepots(cls, produit_id, quantite, entrepot_source_id, entrepot_dest_id, 
                                    utilisateur, reference=None, notes=None, unite_mesure_id=None):
        from ..models import TransfertStock, LigneTransfertStock, SourceOperation, UniteMesure
        
        produit = Produit.objects.get(id=produit_id)
        source = Entrepot.objects.get(id=entrepot_source_id)
        dest = Entrepot.objects.get(id=entrepot_dest_id)

        if source.id == dest.id:
            raise ValueError("L'entrepôt source et destination sont identiques")

        quantite_saisie = Decimal(str(quantite))
        unite_source_obj = None
        
        if unite_mesure_id:
            unite_source_obj = UniteMesure.objects.get(id=unite_mesure_id)
            try:
                quantite_reelle = ConversionUniteService.convertir(
                    quantite=quantite_saisie,
                    unite_source=unite_source_obj,
                    unite_dest=produit.unite_mesure,
                    produit=produit
                )
            except ValidationError as e:
                raise ValueError(str(e))
        else:
            quantite_reelle = quantite_saisie
            
        # Création de la Source Operation
        source_op = SourceOperation.objects.create(
            type_source=SourceOperationType.TRANSFERT,
            reference=reference or "TR",
            notes=notes
        )

        # Création du transfert
        transfert = TransfertStock.objects.create(
            entrepot_source=source,
            entrepot_dest=dest,
            statut='VALIDE',
            source_operation=source_op,
            cree_par=utilisateur if not isinstance(utilisateur, str) else None,
            valide_par=utilisateur if not isinstance(utilisateur, str) else None,
            date_validation=timezone.now(),
            notes=notes
        )
        
        if not reference:
            source_op.reference = transfert.numero
            source_op.save(update_fields=['reference'])
            
        LigneTransfertStock.objects.create(
            transfert=transfert,
            produit=produit,
            quantite=quantite_saisie,
            unite_mesure=unite_source_obj
        )
        
        unite_texte = unite_source_obj.symbole if unite_source_obj else produit.unite_base
        
        # Sortie (lots alloués via FEFO à l'intérieur)
        sortie = MouvementStockService.sortie_stock(
            produit=produit, entrepot=source,
            quantite=quantite_reelle, utilisateur=utilisateur,
            motif=SourceOperationType.TRANSFERT, valeur_unitaire=produit.prix_achat or Decimal('0'),
            reference=transfert.numero,
            raison=f"Transfert vers {dest.nom}",
            entrepot_dest=dest,
            source_operation=source_op,
            type_mouvement_override=TypeMouvement.TRANSFERT_SORTIE
        )
        
        # Entrée (ne génère pas de lots — on les transfère depuis la sortie)
        entree = MouvementStockService.entree_stock(
            produit=produit, entrepot=dest,
            quantite=quantite_reelle, utilisateur=utilisateur,
            motif=SourceOperationType.TRANSFERT, valeur_unitaire=produit.prix_achat or Decimal('0'),
            reference=transfert.numero,
            raison=f"Transfert depuis {source.nom}",
            unite_texte=unite_texte,
            entrepot_source=source,
            source_operation=source_op,
            type_mouvement_override=TypeMouvement.TRANSFERT_ENTREE
        )
        
        # Transférer les allocations de lots de la sortie vers la destination
        from ..models import MouvementLot, StockLotEntrepot
        allocations_sortie = sortie.mouvements_lots.all()
        for alloc in allocations_sortie:
            lot = alloc.lot
            qte = abs(alloc.quantite)
            stock_lot_dest, _ = StockLotEntrepot.objects.select_for_update().get_or_create(
                lot=lot,
                entrepot=dest,
                defaults={'quantite': Decimal('0')}
            )
            stock_lot_dest.quantite += qte
            stock_lot_dest.save(update_fields=['quantite'])
            
            MouvementLot.objects.create(
                mouvement=entree,
                lot=lot,
                quantite=qte
            )
        
        return transfert
    

    @classmethod
    def get_stock_entrepot(cls, code_entrepot, produit_id=None):
        """Récupère le stock d'un entrepôt"""
        from ..models import StockEntrepot
        try:
            entrepot = Entrepot.objects.get(code=code_entrepot)
        except Entrepot.DoesNotExist:
            entrepot = Entrepot.objects.filter(type_entrepot=code_entrepot).first()
            if not entrepot:
                raise Exception(f"Entrepôt {code_entrepot} non trouvé")
        
        stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit')
        
        if produit_id:
            stocks = stocks.filter(produit_id=produit_id)
        
        return stocks

    @classmethod
    @transaction.atomic
    def annuler_transfert(cls, transfert_ou_numero, user):
        """Annule un transfert (SORTIE + ENTREE inversées)."""
        from ..models import TransfertStock, MouvementStock, SourceOperation
        
        if isinstance(transfert_ou_numero, str):
            transfert = TransfertStock.objects.get(numero=transfert_ou_numero)
        else:
            transfert = transfert_ou_numero
            
        if transfert.statut == 'ANNULE':
            raise ValueError("Ce transfert est déjà annulé.")
            
        source_op = transfert.source_operation
        
        # Trouver les mouvements liés à ce transfert
        sorties = MouvementStock.objects.filter(
            source_operation=source_op,
            type_mouvement=TypeMouvement.TRANSFERT_SORTIE
        )
        entrees = MouvementStock.objects.filter(
            source_operation=source_op,
            type_mouvement=TypeMouvement.TRANSFERT_ENTREE
        )
        
        # On va créer une nouvelle source pour l'annulation
        source_annulation = SourceOperation.objects.create(
            type_source=SourceOperationType.ANNULATION,
            reference=f"ANNUL-{transfert.numero}",
            notes=f"Annulation du transfert {transfert.numero}"
        )
        
        from .lot_allocation_service import LotAllocationService
        
        # Inverser l'entrée (faire une sortie de la destination avec restitution exacte des lots)
        for entree in entrees:
            sortie_annul = MouvementStockService.sortie_stock(
                produit=entree.produit,
                entrepot=entree.entrepot_dest,
                quantite=entree.quantite,
                utilisateur=user,
                motif=SourceOperationType.ANNULATION,
                valeur_unitaire=entree.valeur_unitaire,
                reference=source_annulation.reference,
                raison=f"Annulation transfert {transfert.numero} - Sortie dest",
                source_operation=source_annulation,
                type_mouvement_override=TypeMouvement.SORTIE,
                skip_fefo=True
            )
            # Restaurer les lots exacts dans l'entrepôt source
            LotAllocationService.inverser_allocations(
                mouvement_original=entree,
                mouvement_inverse=sortie_annul
            )
            
        # Inverser la sortie (faire une entrée dans la source)
        for sortie in sorties:
            entree_annul = MouvementStockService.entree_stock(
                produit=sortie.produit,
                entrepot=sortie.entrepot_source,
                quantite=sortie.quantite,
                utilisateur=user,
                motif=SourceOperationType.ANNULATION,
                valeur_unitaire=sortie.valeur_unitaire,
                reference=source_annulation.reference,
                raison=f"Annulation transfert {transfert.numero} - Retour source",
                source_operation=source_annulation,
                type_mouvement_override=TypeMouvement.ENTREE
            )
            # Restaurer les lots exacts dans l'entrepôt source
            LotAllocationService.inverser_allocations(
                mouvement_original=sortie,
                mouvement_inverse=entree_annul
            )
            
        transfert.statut = 'ANNULE'
        transfert.save(update_fields=['statut'])
        
        return transfert

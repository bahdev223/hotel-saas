# apps/stock/services/lot_allocation_service.py
from decimal import Decimal
from django.db import transaction, models
from django.db.models import Sum
from django.utils import timezone
from ..models import Produit, Entrepot, LotProduit, StockLotEntrepot, MouvementStock, MouvementLot
from django.core.exceptions import ValidationError

class LotAllocationService:
    """Service gérant l'allocation et le suivi des lots (FEFO)."""
    
    @classmethod
    @transaction.atomic
    def entree_lot(cls, mouvement, lot_numero, quantite, date_peremption=None, fournisseur_id=None):
        """
        Gère l'entrée en stock pour un lot spécifique lié à un mouvement.
        """
        produit = mouvement.produit
        entrepot = mouvement.entrepot_dest or mouvement.entrepot_source
        
        if not entrepot:
            raise ValidationError("Le mouvement doit avoir un entrepôt cible.")
            
        # Trouver ou créer le LotProduit
        lot, created = LotProduit.objects.get_or_create(
            produit=produit,
            numero=lot_numero,
            defaults={
                'date_peremption': date_peremption,
                'fournisseur_id': fournisseur_id,
                'actif': True
            }
        )
        
        # S'il existait déjà et n'était plus actif, on le réactive si on ajoute du stock
        if not lot.actif:
            lot.actif = True
            lot.save(update_fields=['actif'])
            
        # Gérer la quantité dans l'entrepôt (with lock)
        stock_lot, created = StockLotEntrepot.objects.select_for_update().get_or_create(
            lot=lot,
            entrepot=entrepot,
            defaults={'quantite': Decimal('0')}
        )
        stock_lot.quantite += Decimal(str(quantite))
        stock_lot.save(update_fields=['quantite'])
        
        # Enregistrer la liaison Mouvement <-> Lot
        MouvementLot.objects.create(
            mouvement=mouvement,
            lot=lot,
            quantite=quantite
        )
        
        return lot
        
    @classmethod
    @transaction.atomic
    def allouer_lots_fefo(cls, mouvement, quantite_a_allouer):
        """
        Alloue automatiquement les lots selon la méthode FEFO 
        (First Expired, First Out) pour un mouvement de sortie.
        Retourne la liste des lots alloués et leurs quantités.
        """
        quantite_a_allouer = Decimal(str(quantite_a_allouer))
        produit = mouvement.produit
        entrepot = mouvement.entrepot_source
        
        if not entrepot:
            raise ValidationError("Le mouvement de sortie doit avoir un entrepôt source.")
            
        # Pre-check total available before mutating
        stocks_lots_dispos = StockLotEntrepot.objects.filter(
            lot__produit=produit,
            entrepot=entrepot,
            quantite__gt=0,
            lot__actif=True
        )
        
        total_disponible = stocks_lots_dispos.aggregate(
            total=Sum("quantite")
        )["total"] or Decimal("0")
        
        if total_disponible < quantite_a_allouer:
            raise ValidationError(
                f"Stock lot insuffisant pour {produit.nom} dans {entrepot.nom}. "
                f"Disponible: {total_disponible}, demandé: {quantite_a_allouer} {produit.unite_base}"
            )
            
        # Lock and order FEFO
        stocks_lots_verrouilles = stocks_lots_dispos.select_for_update().order_by(
            models.F('lot__date_peremption').asc(nulls_last=True),
            'lot__date_creation'
        )
        
        quantite_restante = quantite_a_allouer
        allocations = []
        
        for stock_lot in stocks_lots_verrouilles:
            if quantite_restante <= 0:
                break
                
            quantite_prise = min(stock_lot.quantite, quantite_restante)
            stock_lot.quantite -= quantite_prise
            stock_lot.save(update_fields=['quantite'])
            
            # Lier la sortie au lot
            MouvementLot.objects.create(
                mouvement=mouvement,
                lot=stock_lot.lot,
                quantite=-quantite_prise
            )
            
            allocations.append((stock_lot.lot, quantite_prise))
            quantite_restante -= quantite_prise
            
        return allocations
    
    @classmethod
    @transaction.atomic
    def inverser_allocations(cls, mouvement_original, mouvement_inverse):
        """
        Inverse exactement les allocations de lots d'un mouvement original.
        Remplace les lots alloués par FEFO (potentiellement erronés) par
        les lots exacts du mouvement original.
        Utilisé lors de l'annulation d'un transfert pour garantir
        que les mêmes lots sont restitués.
        """
        # Supprimer les allocations FEFO automatiques (peuvent être incorrectes)
        MouvementLot.objects.filter(mouvement=mouvement_inverse).delete()
        
        # Restaurer les allocations exactes du mouvement original
        originales = MouvementLot.objects.filter(
            mouvement=mouvement_original
        ).select_related('lot')
        
        for alloc in originales:
            lot = alloc.lot
            # Signe opposé à l'original
            # Si original était positif (entrée), l'inverse est négatif (sortie)
            # Si original était négatif (sortie), l'inverse est positif (entrée)
            qte = -alloc.quantite
            
            entrepot = (mouvement_inverse.entrepot_source 
                       or mouvement_inverse.entrepot_dest)
            
            stock_lot = StockLotEntrepot.objects.select_for_update().get(
                lot=lot,
                entrepot=entrepot
            )
            stock_lot.quantite += qte
            stock_lot.save(update_fields=['quantite'])
            
            MouvementLot.objects.create(
                mouvement=mouvement_inverse,
                lot=lot,
                quantite=qte
            )

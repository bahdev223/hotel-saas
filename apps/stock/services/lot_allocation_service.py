# apps/stock/services/lot_allocation_service.py
from decimal import Decimal
from django.db import transaction, models
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
            
        # Gérer la quantité dans l'entrepôt
        stock_lot, created = StockLotEntrepot.objects.get_or_create(
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
            
        # Récupérer les lots disponibles pour ce produit dans cet entrepôt
        stocks_lots_dispos = StockLotEntrepot.objects.filter(
            lot__produit=produit,
            entrepot=entrepot,
            quantite__gt=0,
            lot__actif=True
        ).order_by(
            models.F('lot__date_peremption').asc(nulls_last=True),
            'lot__date_creation'
        )
        
        quantite_restante = quantite_a_allouer
        allocations = []
        
        for stock_lot in stocks_lots_dispos:
            if quantite_restante <= 0:
                break
                
            quantite_prise = min(stock_lot.quantite, quantite_restante)
            stock_lot.quantite -= quantite_prise
            stock_lot.save(update_fields=['quantite'])
            
            # Lier la sortie au lot
            MouvementLot.objects.create(
                mouvement=mouvement,
                lot=stock_lot.lot,
                quantite=-quantite_prise # Négatif pour indiquer une sortie de ce lot ? Ou juste quantité et on déduit du contexte ? Le MouvementStock a le type, la quantité est absolue.
            )
            
            allocations.append((stock_lot.lot, quantite_prise))
            quantite_restante -= quantite_prise
            
        if quantite_restante > 0:
            raise ValidationError(
                f"Impossible d'allouer {quantite_a_allouer} {produit.unite_base}. "
                f"Il manque {quantite_restante} dans les lots disponibles de l'entrepôt {entrepot.nom}."
            )
            
        return allocations

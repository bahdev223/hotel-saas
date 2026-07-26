# apps/stock/services/lot_allocation_service.py
from datetime import timedelta
from decimal import Decimal
from django.db import transaction, models
from django.db.models import Sum, F, Q
from django.utils import timezone
from ..models import (
    Produit, Entrepot, LotProduit, StockLotEntrepot,
    StockEntrepot, MouvementStock, MouvementLot,
)
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
            
        # Lock and order FEFO (tiebreaker = pk pour éviter deadlocks)
        stocks_lots_verrouilles = stocks_lots_dispos.select_for_update().order_by(
            models.F('lot__date_peremption').asc(nulls_last=True),
            'lot__date_creation',
            'pk'
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

    @classmethod
    def verifier_coherence(cls, entrepot=None, produit=None):
        """
        Vérifie que la somme des StockLotEntrepot correspond au StockEntrepot.
        Retourne la liste des écarts constatés.
        """
        qs_stock = StockEntrepot.objects.select_related('produit', 'entrepot').all()
        if entrepot:
            qs_stock = qs_stock.filter(entrepot=entrepot)
        if produit:
            qs_stock = qs_stock.filter(produit=produit)

        ecarts = []
        for se in qs_stock:
            somme_lots = StockLotEntrepot.objects.filter(
                lot__produit=se.produit,
                entrepot=se.entrepot,
                lot__actif=True,
            ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')

            if se.quantite != somme_lots:
                ecarts.append({
                    'produit': se.produit.nom,
                    'produit_id': se.produit_id,
                    'entrepot': se.entrepot.nom,
                    'stock_entrepot': se.quantite,
                    'somme_lots': somme_lots,
                    'ecart': se.quantite - somme_lots,
                })

        return ecarts

    @classmethod
    def alertes_peremption(cls, jours=7, entrepot=None):
        """
        Retourne les lots dont la date de péremption est dans moins de `jours`
        jours, avec quantité > 0.
        """
        seuil = timezone.now().date() + timedelta(days=jours)

        qs = StockLotEntrepot.objects.filter(
            lot__date_peremption__lte=seuil,
            lot__date_peremption__gte=timezone.now().date(),
            lot__actif=True,
            quantite__gt=0,
        ).select_related('lot__produit', 'lot__fournisseur', 'entrepot')

        if entrepot:
            qs = qs.filter(entrepot=entrepot)

        return [
            {
                'lot_id': sle.lot_id,
                'lot_numero': sle.lot.numero,
                'produit': sle.lot.produit.nom,
                'entrepot': sle.entrepot.nom,
                'quantite': sle.quantite,
                'date_peremption': sle.lot.date_peremption,
                'jours_restants': (sle.lot.date_peremption - timezone.now().date()).days,
                'fournisseur': sle.lot.fournisseur.nom if sle.lot.fournisseur else None,
            }
            for sle in qs
        ]

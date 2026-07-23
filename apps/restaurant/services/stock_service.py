# apps/restaurant/services/stock_service.py
from django.db import transaction
from decimal import Decimal
from apps.stock.models import Produit, StockEntrepot, MouvementStock, Entrepot


class StockService:
    """Service de gestion des stocks pour le restaurant"""
    
    @staticmethod
    def get_stock_entrepot(produit, entrepot):
        """Récupère le stock d'un produit dans un entrepôt"""
        stock = StockEntrepot.objects.filter(
            entrepot=entrepot,
            produit=produit
        ).first()
        return stock.quantite if stock else Decimal('0')
    
    @staticmethod
    @transaction.atomic
    def consommer_ingredient(produit, entrepot, quantite, utilisateur, reference="", raison=""):
        """Consomme un ingrédient du stock"""
        stock = StockEntrepot.objects.select_for_update().get(
            entrepot=entrepot,
            produit=produit
        )
        
        if stock.quantite < quantite:
            raise ValueError(f"Stock insuffisant pour {produit.nom}")
        
        stock.quantite -= quantite
        stock.save()
        
        MouvementStock.objects.create(
            produit=produit,
            type_mouvement='SORTIE',
            quantite=quantite,
            entrepot_source=entrepot,
            utilisateur=utilisateur,
            reference=reference,
            raison=raison
        )
        
        return stock
    
    @staticmethod
    @transaction.atomic
    def ajouter_stock(produit, entrepot, quantite, utilisateur, reference="", raison=""):
        """Ajoute du stock à un entrepôt"""
        stock, created = StockEntrepot.objects.get_or_create(
            entrepot=entrepot,
            produit=produit,
            defaults={'quantite': Decimal('0')}
        )
        
        stock.quantite += quantite
        stock.save()
        
        MouvementStock.objects.create(
            produit=produit,
            type_mouvement='ENTREE',
            quantite=quantite,
            entrepot_dest=entrepot,
            utilisateur=utilisateur,
            reference=reference,
            raison=raison
        )
        
        return stock
    
    @staticmethod
    def transferer_stock(produit, source_entrepot, dest_entrepot, quantite, utilisateur, reference=""):
        """Transfère du stock entre entrepôts"""
        from apps.stock.services.transfert_service import TransfertService
        
        return TransfertService.transfert_entre_entrepots(
            produit_id=produit.id,
            quantite=quantite,
            entrepot_source_id=source_entrepot.id,
            entrepot_dest_id=dest_entrepot.id,
            utilisateur=utilisateur,
            reference=reference
        )
    
    @staticmethod
    def get_produits_alertes(entrepot):
        """Récupère les produits en alerte de stock"""
        stocks = StockEntrepot.objects.filter(
            entrepot=entrepot,
            quantite__lte=models.F('produit__seuil_alerte'),
            quantite__gt=0
        ).select_related('produit')
        
        return [
            {
                'produit': s.produit,
                'stock': s.quantite,
                'seuil': s.produit.seuil_alerte
            }
            for s in stocks
        ]
    
    @staticmethod
    def get_produits_rupture(entrepot):
        """Récupère les produits en rupture"""
        stocks = StockEntrepot.objects.filter(
            entrepot=entrepot,
            quantite__lte=0
        ).select_related('produit')
        
        return [s.produit for s in stocks]
    
    
    
# apps/facturation/services/mixins/total_mixin.py
from decimal import Decimal


class TotalMixin:
    """Mixin pour le calcul des totaux"""
    
    @staticmethod
    def calculer_total_ht(lignes):
        """Calcule le total HT d'une liste de lignes"""
        total = Decimal('0')
        for ligne in lignes:
            total += ligne.get('quantite', 1) * ligne.get('prix_unitaire', 0)
        return total
    
    @staticmethod
    def calculer_total_tva(lignes):
        """Calcule le total TVA d'une liste de lignes"""
        from .tva_mixin import TVAMixin
        
        total = Decimal('0')
        for ligne in lignes:
            montant_ht = ligne.get('quantite', 1) * ligne.get('prix_unitaire', 0)
            tva = TVAMixin.calculer_tva(montant_ht, ligne.get('tva', 18))
            total += tva
        return total
    
    @staticmethod
    def calculer_total_ttc(lignes):
        """Calcule le total TTC d'une liste de lignes"""
        from .tva_mixin import TVAMixin
        
        total = Decimal('0')
        for ligne in lignes:
            montant_ht = ligne.get('quantite', 1) * ligne.get('prix_unitaire', 0)
            total += TVAMixin.calculer_ttc(montant_ht, ligne.get('tva', 18))
        return total
    
    @staticmethod
    def cumuler_paiements(paiements):
        """Cumule le montant total des paiements"""
        total = Decimal('0')
        for paiement in paiements:
            total += paiement.get('montant', 0)
        return total
    
    @staticmethod
    def calculer_reste(montant_total, montant_paye):
        """Calcule le reste à payer"""
        return montant_total - montant_paye
    
    
# apps/facturation/services/mixins/tva_mixin.py
from decimal import Decimal


class TVAMixin:
    """Mixin pour la gestion de la TVA"""
    
    # TVA par défaut au Mali
    TAUX_TVA_DEFAUT = Decimal('18')
    
    @classmethod
    def calculer_tva(cls, montant_ht, taux=None):
        """Calcule la TVA à partir du montant HT"""
        if taux is None:
            taux = cls.TAUX_TVA_DEFAUT
        return montant_ht * (taux / 100)
    
    @classmethod
    def calculer_ttc(cls, montant_ht, taux=None):
        """Calcule le montant TTC à partir du HT"""
        tva = cls.calculer_tva(montant_ht, taux)
        return montant_ht + tva
    
    @classmethod
    def calculer_ht_depuis_ttc(cls, montant_ttc, taux=None):
        """Calcule le montant HT à partir du TTC"""
        if taux is None:
            taux = cls.TAUX_TVA_DEFAUT
        return montant_ttc / (1 + (taux / 100))
    
    @classmethod
    def appliquer_tva_aux_lignes(cls, lignes):
        """Applique la TVA à chaque ligne et retourne le total TTC"""
        total_ttc = Decimal('0')
        for ligne in lignes:
            total_ligne = ligne.get('quantite', 1) * ligne.get('prix_unitaire', 0)
            tva = cls.calculer_tva(total_ligne, ligne.get('tva', cls.TAUX_TVA_DEFAUT))
            total_ttc += total_ligne + tva
        return total_ttc
    
    
    
    
    
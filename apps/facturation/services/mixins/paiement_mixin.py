# apps/facturation/services/mixins/paiement_mixin.py
from decimal import Decimal
from django.contrib.contenttypes.models import ContentType
from django.db import models

from apps.paiements.models import Paiement


class PaiementMixin:
    """Mixin pour la gestion des paiements liés aux factures"""
    
    @staticmethod
    def get_paiements_facture(facture):
        """Récupère tous les paiements d'une facture"""
        from apps.paiements.models import Paiement
        
        content_type = ContentType.objects.get_for_model(facture)
        return Paiement.objects.filter(
            content_type=content_type,
            object_id=facture.id,
            statut='VALIDE'
        )
    
    @staticmethod
    def get_total_paye(facture):
        """Calcule le total payé pour une facture"""
        paiements = PaiementMixin.get_paiements_facture(facture)
        total = paiements.aggregate(total=models.Sum('montant'))['total'] or Decimal('0')
        return total
    
    @staticmethod
    def get_total_encaisse(facture, caisse_id=None):
        """Calcule le total encaissé pour une facture (optionnellement par caisse)"""
        paiements = PaiementMixin.get_paiements_facture(facture)
        if caisse_id:
            paiements = paiements.filter(caisse_id=caisse_id)
        return paiements.aggregate(total=models.Sum('montant'))['total'] or Decimal('0')
    
    @staticmethod
    def get_repartition_paiements(facture):
        """Récupère la répartition des paiements par mode"""
        paiements = PaiementMixin.get_paiements_facture(facture)
        
        repartition = {}
        for mode, _ in Paiement.MODE_CHOICES:
            total = paiements.filter(mode=mode).aggregate(total=models.Sum('montant'))['total'] or Decimal('0')
            if total > 0:
                repartition[mode] = total
        
        return repartition
    
    @staticmethod
    def verifier_solde(facture):
        """Vérifie si la facture est entièrement payée"""
        from .total_mixin import TotalMixin
        
        total_paye = PaiementMixin.get_total_paye(facture)
        reste = TotalMixin.calculer_reste(facture.montant_total, total_paye)
        return reste <= 0, reste
    
        
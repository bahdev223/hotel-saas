# apps/facturation/services/actions.py
from decimal import Decimal
from django.db import models
from django.contrib.contenttypes.models import ContentType
from ..models import FactureModel


class FactureActions:
    """Actions sur les factures (émettre, payer, annuler, recalculer)"""
    
    @staticmethod
    def emettre(facture_id):
        """Émet une facture (BROUILLON → EMISE)"""
        facture = FactureModel.objects.get(id=facture_id)
        facture.emettre()
        return facture
    
    @staticmethod
    def annuler(facture_id):
        """Annule une facture"""
        facture = FactureModel.objects.get(id=facture_id)
        facture.annuler()
        return facture
    
    @staticmethod
    def marquer_payee(facture_id):
        """Marque une facture comme payée (si soldée)"""
        facture = FactureModel.objects.get(id=facture_id)
        if facture.reste_a_payer <= 0:
            facture.statut = 'PAYEE'
            facture.save()
            return True
        return False
    
    @staticmethod
    def verifier_et_mettre_a_jour_statut(facture):
        """Vérifie le solde et met à jour le statut automatiquement"""
        from .base import BaseFactureService
        
        total_paye = BaseFactureService.get_total_paye(facture)
        if total_paye >= facture.montant_total:
            facture.statut = 'PAYEE'
            facture.save()
            return True
        elif facture.statut == 'PAYEE' and total_paye < facture.montant_total:
            facture.statut = 'EMISE'
            facture.save()
        return False
    
    @staticmethod
    def recalculer(facture_id):
        """Recalcule le total et le statut d'une facture"""
        facture = FactureModel.objects.get(id=facture_id)
        # Le montant_total est une property (calculé depuis les lignes)
        FactureActions.verifier_et_mettre_a_jour_statut(facture)
        return facture

        
        
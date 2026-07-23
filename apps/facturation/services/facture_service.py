# apps/facturation/services/facture_service.py
from ..models import FactureModel


class FactureService:
    """Orchestrateur - gestion globale des factures"""
    
    @staticmethod
    def emettre(facture_id):
        """Émettre une facture"""
        facture = FactureModel.objects.get(id=facture_id)
        facture.emettre()
        return facture
    
    @staticmethod
    def annuler(facture_id):
        """Annuler une facture"""
        facture = FactureModel.objects.get(id=facture_id)
        facture.annuler()
        return facture
    
    @staticmethod
    def marquer_payee(facture_id):
        """Marquer une facture comme payée"""
        facture = FactureModel.objects.get(id=facture_id)
        facture.marquer_payee()
        return facture
    
    @staticmethod
    def recalculer(facture_id):
        """Recalculer le total d'une facture (si nécessaire)"""
        facture = FactureModel.objects.get(id=facture_id)
        # Le montant_total est une property, donc automatique
        if facture.est_payee:
            facture.statut = 'PAYEE'
            facture.save()
        return facture
    
    
    
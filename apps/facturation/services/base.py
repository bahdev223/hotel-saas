# apps/facturation/services/base.py
from decimal import Decimal
from django.db import models
from django.contrib.contenttypes.models import ContentType
from ..models import FactureModel, LigneFactureModel


class BaseFactureService:
    """Noyau commun à tous les services de facturation"""
    
    @staticmethod
    def creer_facture(client_nom, client=None, location=None, commande=None, notes=""):
        """Crée une facture vide (BROUILLON)"""
        return FactureModel.objects.create(
            location=location,
            commande=commande,
            client=client,
            client_nom=client_nom,
            statut='BROUILLON',
            notes=notes
        )
    
    @staticmethod
    def ajouter_ligne(facture, description, quantite, prix_unitaire, tva=18):
        """Ajoute une ligne à une facture"""
        return LigneFactureModel.objects.create(
            facture=facture,
            description=description,
            quantite=quantite,
            prix_unitaire=prix_unitaire,
            tva=tva
        )
    
    @staticmethod
    def calculer_total_ttc(lignes):
        """Calcule le total TTC d'une liste de lignes"""
        return sum(l.total_ttc for l in lignes)
    
    @staticmethod
    def get_total_paye(facture):
        """Calcule le total payé depuis apps.paiements"""
        from apps.paiements.models import Paiement
        
        ct = ContentType.objects.get_for_model(facture)
        total = Paiement.objects.filter(
            content_type=ct,
            object_id=facture.pk,
            statut='VALIDE',
            sens='ENTREE'
        ).aggregate(total=models.Sum('montant'))['total'] or Decimal('0')
        return total
    
    
# apps/facturation/services/generators.py
from .base import BaseFactureService


class FactureGenerators(BaseFactureService):
    """Génération de factures par type de flux"""
    
    @staticmethod
    def depuis_location(location):
        """Génère une facture à partir d'une location (hôtel)"""
        
        # Vérifier si une facture existe déjà
        if hasattr(location, 'facture') and location.facture:
            return location.facture
        
        facture = BaseFactureService.creer_facture(
            client_nom=location.client.nom_complet,
            client=location.client,
            location=location,
            notes=f"Facture pour {location.get_type_location_display()}"
        )
        
        # Ligne principale
        type_labels = {'CHAMBRE': 'Chambre', 'SALLE': 'Salle', 'ESPACE': 'Espace', 'ESPACE_BAR': 'Espace + Bar', 'BAR': 'Bar VIP'}
        label = type_labels.get(location.type_location, 'Location')
        description = f"{label} - {location.unite.nom} - {location.duree_display}"
        
        BaseFactureService.ajouter_ligne(
            facture=facture,
            description=description,
            quantite=1,
            prix_unitaire=location.montant_total,
            tva=0
        )
        
        return facture
    
    @staticmethod
    def depuis_commande(commande):
        """Génère une facture à partir d'une commande (restaurant)"""
        
        if hasattr(commande, 'facture') and commande.facture:
            return commande.facture
        
        facture = BaseFactureService.creer_facture(
            client_nom=commande.client.nom_complet if commande.client else (commande.client_nom or 'Client'),
            client=commande.client,
            commande=commande,
            notes=f"Commande #{commande.numero}"
        )
        
        for ligne in commande.lignes.all():
            if ligne.unite:
                quantite = float(ligne.heures or 1)
                tva = 0
            else:
                quantite = float(ligne.quantite)
                tva = 18
            BaseFactureService.ajouter_ligne(
                facture=facture,
                description=ligne.article_nom,
                quantite=quantite,
                prix_unitaire=float(ligne.prix_unitaire),
                tva=tva
            )
        
        return facture
    
    @staticmethod
    def depuis_vente(vente):
        """Génère une facture à partir d'une vente directe (POS)"""
        
        facture = BaseFactureService.creer_facture(
            client_nom=vente.client.nom_complet if vente.client else (vente.client_nom or 'Client'),
            client=vente.client,
            notes=f"Vente #{vente.numero}"
        )
        
        for ligne in vente.lignes.all():
            BaseFactureService.ajouter_ligne(
                facture=facture,
                description=ligne.article_nom,
                quantite=float(ligne.quantite),
                prix_unitaire=float(ligne.prix_unitaire),
                tva=18
            )
        
        return facture
    
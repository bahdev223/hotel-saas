"""
Service de facturation pour le restaurant
Délègue tout au module facturation centralisé
"""

from decimal import Decimal


class RestaurantFacturationService:
    """Service de facturation pour le restaurant"""

    @classmethod
    def generer_facture_depuis_vente(cls, vente_id: str, client_nom: str = None):
        from ..models import VenteModel
        from ...facturation.services import FactureGenerators

        vente = VenteModel.objects.get(id=vente_id)
        facture = FactureGenerators.depuis_vente(vente)
        if facture.statut == 'BROUILLON':
            facture.emettre()
            facture.marquer_payee()
        return facture

    @classmethod
    def generer_facture_depuis_commande(cls, commande_id: str, lignes_data: list,
                                         total: Decimal, mode_paiement: str,
                                         encaisse_par: str, client_nom: str = None):
        from ...facturation.models import FactureModel
        from ...facturation.services import BaseFactureService, FactureActions

        facture = BaseFactureService.creer_facture(
            client_nom=client_nom or 'Client',
            notes=f"Commande restaurant #{commande_id}"
        )

        for ligne in lignes_data:
            quantite = Decimal(str(ligne['quantite']))
            prix_unitaire = Decimal(str(ligne['prix']))
            BaseFactureService.ajouter_ligne(
                facture=facture,
                description=ligne['nom'],
                quantite=quantite,
                prix_unitaire=prix_unitaire,
                tva=18
            )

        facture.emettre()
        facture.marquer_payee()
        return facture

    @classmethod
    def get_factures_restaurant(cls, date_debut=None, date_fin=None):
        from ...facturation.models import FactureModel

        factures = FactureModel.objects.exclude(commande__isnull=True)
        if date_debut:
            factures = factures.filter(date_emission__gte=date_debut)
        if date_fin:
            factures = factures.filter(date_emission__lte=date_fin)
        return factures.order_by('-date_emission')

    @classmethod
    def get_ca_restaurant(cls, date_debut=None, date_fin=None) -> Decimal:
        factures = cls.get_factures_restaurant(date_debut, date_fin)
        return Decimal(str(sum(float(f.montant_total) for f in factures)))

from decimal import Decimal
from django.db import transaction, models
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from apps.paiements.models import Paiement
from apps.tresorerie.services.mouvement_service import MouvementService
from apps.comptabilite.services import EcritureComptableService


class AnnulationService:

    @staticmethod
    @transaction.atomic
    def annuler_commande(commande, user):
        """Annule une commande PAYEE et rembobine tout (stock, paiement, caisse, compta)."""
        from apps.pos.models import Commande, Vente
        from apps.stock.services.mouvement_service import MouvementStockService
        from apps.clients.models import Client

        # 1. Lock the Commande
        commande = Commande.objects.select_for_update().get(id=commande.id)

        if commande.statut not in ('PAYEE',):
            raise ValueError("Seules les commandes PAYÉES peuvent être annulées")

        vente = commande.vente
        if not vente:
            raise ValueError("Aucune vente associée à cette commande")

        # 2. Lock the Vente
        vente = Vente.objects.select_for_update().get(id=vente.id)

        # 3. Trouver les Paiements liés à cette Commande
        ct_commande = ContentType.objects.get_for_model(Commande)
        paiements = Paiement.objects.select_for_update().filter(
            content_type=ct_commande,
            object_id=str(commande.id),
            statut='VALIDE'
        )

        for paiement in paiements:
            AnnulationService._annuler_paiement(paiement, user)

        # 4. Reverser le stock
        AnnulationService._reverser_stock(commande, vente, user)

        # 5. Marquer la Vente ANNULEE
        vente.statut = 'ANNULEE'
        vente.save()

        # 6. Marquer la Commande ANNULEE
        commande.statut = 'ANNULEE'
        commande.save()

        return commande

    @staticmethod
    def _annuler_paiement(paiement, user):
        """Annule un paiement selon son mode."""
        from apps.comptabilite.models import CompteClient, ExerciceModel
        from datetime import date

        if paiement.mode in ('CREDIT', 'SOLDE'):
            # CREDIT/SOLDE : pas de mouvement caisse → on reverse juste CompteClient
            AnnulationService._reverser_compte_client(paiement, signe='+')
            paiement.statut = 'ANNULE'
            paiement.save()
        else:
            # ESPECES, CARTE, MOBILE_MONEY, CHEQUE, VIREMENT
            paiement.annuler(user, raison="Annulation commande RAF")

    @staticmethod
    def _reverser_compte_client(paiement, signe='+'):
        """Ajoute ou retire le montant du CompteClient."""
        from apps.comptabilite.models import CompteClient, ExerciceModel
        from datetime import date
        from decimal import Decimal

        client = paiement.client
        if not client:
            # Chercher le client via le content_object
            obj = paiement.objet
            if obj and hasattr(obj, 'client') and obj.client:
                client = obj.client
        if not client:
            return

        exercice = ExerciceModel.objects.filter(
            date_debut__lte=date.today(),
            date_fin__gte=date.today(),
            cloture=False
        ).first()
        if not exercice:
            exercice = ExerciceModel.objects.filter(cloture=False).first()
        if not exercice:
            return

        compte, _ = CompteClient.objects.select_for_update().get_or_create(
            client=client, exercice=exercice
        )
        montant = Decimal(str(paiement.montant))
        if signe == '+':
            compte.solde += montant  # rembourse le crédit
        else:
            compte.solde -= montant
        compte.save()

    @staticmethod
    def _reverser_stock(commande, vente, user):
        """Remet le stock consommé par la commande."""
        if getattr(commande.point_vente, "type", None) == "RESTAURATION":
            from apps.restaurant.services.consumption_service import RestaurantConsumptionService
            RestaurantConsumptionService.annuler_consommation_commande(
                commande,
                utilisateur=user,
            )
            return

        from apps.stock.enums.sources import SourceOperationType
        from apps.stock.services.mouvement_service import MouvementStockService
        from apps.pos.models import PointVenteEntrepot

        entrepot = commande.entrepot
        if not entrepot:
            liaison = (
                PointVenteEntrepot.objects
                .filter(
                    point_vente=commande.point_vente,
                    actif=True,
                    autorise_retour=True,
                    entrepot__actif=True,
                )
                .select_related("entrepot")
                .order_by("-principal", "priorite", "id")
                .first()
            )
            entrepot = liaison.entrepot if liaison else None
        if not entrepot:
            return

        for ligne in commande.lignes.all():
            produit = ligne.produit
            if not produit:
                continue
            quantite = ligne.quantite
            if getattr(ligne, "unite_id", None) and getattr(ligne, "heures", None):
                quantite = ligne.heures

            MouvementStockService.entree_stock(
                produit=produit,
                entrepot=entrepot,
                quantite=quantite,
                utilisateur=user,
                motif=SourceOperationType.ANNULATION,
                reference=f"ANN-{commande.numero}",
                raison=f"Annulation commande #{commande.numero}",
            )

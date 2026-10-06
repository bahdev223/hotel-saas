from django.db import transaction
from django.utils import timezone

from apps.pos.constants import ActionPOS, TypePointVente
from apps.pos.models import Commande
from apps.pos.services.access_service import POSAccessService
from apps.restaurant.models import TableModel
from apps.restaurant.services.consumption_service import RestaurantConsumptionService


ACTIVE_ORDER_STATUSES = (
    "EN_ATTENTE",
    "EN_PREPARATION",
    "PRETE",
    "SERVIE",
)


class RestaurantWorkflowError(ValueError):
    pass


class RestaurantService:
    @staticmethod
    def _assert_restaurant(commande_or_point):
        point = getattr(commande_or_point, "point_vente", commande_or_point)
        if not point or point.type != TypePointVente.RESTAURATION:
            raise RestaurantWorkflowError("Opération réservée au Restaurant.")
        return point

    @staticmethod
    def _assert_action(user, point_vente, action):
        decision = POSAccessService.check(
            user=user,
            point_vente=point_vente,
            action=action,
        )
        if not decision.allowed:
            raise RestaurantWorkflowError(
                f"Action Restaurant refusée ({decision.reason})."
            )
        return decision

    @classmethod
    def commande_active_table(cls, table, exclude_commande_id=None):
        qs = Commande.objects.filter(
            table=table,
            point_vente__type=TypePointVente.RESTAURATION,
            statut__in=ACTIVE_ORDER_STATUSES,
            vente__isnull=True,
        )
        if exclude_commande_id:
            qs = qs.exclude(pk=exclude_commande_id)
        return qs.select_related("created_by", "point_vente").order_by("-created_at").first()

    @classmethod
    @transaction.atomic
    def occuper_table(cls, *, table, employe, user, nombre_couverts=None):
        table = TableModel.objects.select_for_update().select_related(
            "salle__point_vente"
        ).get(pk=table.pk)
        point = table.point_vente
        if not point:
            raise RestaurantWorkflowError("Cette table n'est rattachée à aucune salle Restaurant.")
        cls._assert_action(user, point, ActionPOS.GERER_SALLE)
        if not table.actif or table.statut == "HORS_SERVICE":
            raise RestaurantWorkflowError("Cette table est hors service.")
        if cls.commande_active_table(table):
            raise RestaurantWorkflowError("Cette table possède déjà une commande active.")

        table.statut = "OCCUPEE"
        table.serveur_actuel = employe
        table.heure_arrivee = table.heure_arrivee or timezone.now()
        if nombre_couverts is not None:
            couverts = max(1, int(nombre_couverts))
            if couverts > table.capacite:
                raise RestaurantWorkflowError(
                    f"Table {table.numero}: capacité maximale {table.capacite}."
                )
            table.nombre_couverts = couverts
        table.save(update_fields=[
            "statut", "serveur_actuel", "heure_arrivee",
            "nombre_couverts", "updated_at",
        ])
        return table

    @classmethod
    @transaction.atomic
    def lier_commande_table(
        cls,
        *,
        commande,
        table,
        employe,
        user,
        nombre_couverts=None,
    ):
        commande = Commande.objects.select_for_update().select_related(
            "point_vente"
        ).get(pk=commande.pk)
        table = TableModel.objects.select_for_update().select_related(
            "salle__point_vente"
        ).get(pk=table.pk)

        point = cls._assert_restaurant(commande)
        cls._assert_action(user, point, ActionPOS.GERER_SALLE)

        if not table.actif or table.statut == "HORS_SERVICE":
            raise RestaurantWorkflowError("Table indisponible.")
        if not table.salle_id or table.salle.point_vente_id != point.id:
            raise RestaurantWorkflowError(
                "La table n'appartient pas à ce point de vente Restaurant."
            )
        active = cls.commande_active_table(table, exclude_commande_id=commande.id)
        if active:
            raise RestaurantWorkflowError(
                f"Table {table.numero} déjà utilisée par la commande #{active.numero}."
            )

        commande.table = table
        commande.type_commande = "SUR_PLACE"
        commande.save(update_fields=["table", "type_commande", "updated_at"])

        table.statut = "COMMANDE_EN_COURS"
        table.serveur_actuel = employe
        table.heure_arrivee = table.heure_arrivee or timezone.now()
        if nombre_couverts is not None:
            couverts = max(1, int(nombre_couverts))
            if couverts > table.capacite:
                raise RestaurantWorkflowError(
                    f"Table {table.numero}: capacité maximale {table.capacite}."
                )
            table.nombre_couverts = couverts
        elif table.nombre_couverts <= 0:
            table.nombre_couverts = 1
        table.save(update_fields=[
            "statut", "serveur_actuel", "heure_arrivee",
            "nombre_couverts", "updated_at",
        ])
        return commande

    @classmethod
    @transaction.atomic
    def demarrer_preparation(cls, *, commande, user):
        commande = Commande.objects.select_for_update().select_related(
            "point_vente", "entrepot"
        ).get(pk=commande.pk)
        point = cls._assert_restaurant(commande)
        cls._assert_action(user, point, ActionPOS.GERER_CUISINE)
        if commande.statut != "EN_ATTENTE":
            raise RestaurantWorkflowError(
                "Seule une commande en attente peut passer en préparation."
            )

        verification = RestaurantConsumptionService.verifier_disponibilite_commande(
            commande,
            commande.entrepot,
        )
        if not verification["disponible"]:
            raise RestaurantWorkflowError(
                f"Stock insuffisant: {verification['manques']}"
            )

        RestaurantConsumptionService.consommer_commande(
            commande=commande,
            entrepot=commande.entrepot,
            utilisateur=getattr(user, "username", str(user)),
        )
        commande.passer_en_preparation()
        return commande

    @classmethod
    @transaction.atomic
    def marquer_prete(cls, *, commande, user):
        commande = Commande.objects.select_for_update().select_related(
            "point_vente"
        ).get(pk=commande.pk)
        point = cls._assert_restaurant(commande)
        cls._assert_action(user, point, ActionPOS.GERER_CUISINE)
        if commande.statut != "EN_PREPARATION":
            raise RestaurantWorkflowError(
                "Seule une commande en préparation peut être marquée prête."
            )
        commande.marquer_prete()
        return commande

    @classmethod
    @transaction.atomic
    def servir(cls, *, commande, user):
        commande = Commande.objects.select_for_update().select_related(
            "point_vente", "table"
        ).get(pk=commande.pk)
        point = cls._assert_restaurant(commande)
        cls._assert_action(user, point, ActionPOS.SERVIR_COMMANDE)
        if commande.statut != "PRETE":
            raise RestaurantWorkflowError(
                "Seule une commande prête peut être servie."
            )
        commande.servir()
        if commande.table_id:
            table = TableModel.objects.select_for_update().get(pk=commande.table_id)
            table.statut = "A_ENCAISSER"
            table.save(update_fields=["statut", "updated_at"])
        return commande

    @classmethod
    @transaction.atomic
    def liberer_table_si_terminee(cls, commande):
        if not commande.table_id:
            return None
        table = TableModel.objects.select_for_update().get(pk=commande.table_id)
        if cls.commande_active_table(table, exclude_commande_id=commande.id):
            return table

        table.statut = "LIBRE"
        table.serveur_actuel = None
        table.heure_arrivee = None
        table.nombre_couverts = 0
        table.commande_id = None
        table.serveur_id = None
        table.save(update_fields=[
            "statut", "serveur_actuel", "heure_arrivee",
            "nombre_couverts", "commande_id", "serveur_id", "updated_at",
        ])
        return table

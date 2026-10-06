from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from apps.pos.constants import ModeAccesPOS, RolePOS, TypePointVente
from apps.pos.models import AffectationPointVente, Commande, PointVente
from apps.paiements.services.commande_settlement_service import (
    CommandeSettlementError,
    CommandeSettlementService,
)
from apps.restaurant.models import SalleModel, TableModel
from apps.restaurant.services.restaurant_service import (
    RestaurantService,
    RestaurantWorkflowError,
)
from apps.rh.models import Employe


class RestaurantWorkflowTests(TestCase):
    def setUp(self):
        self.restaurant = PointVente.objects.create(
            code="RESTO-V1",
            nom="Restaurant V1",
            type=TypePointVente.RESTAURATION,
            actif=True,
        )
        self.other_restaurant = PointVente.objects.create(
            code="RESTO-V1-B",
            nom="Restaurant B",
            type=TypePointVente.RESTAURATION,
            actif=True,
        )

        self.salle = SalleModel.objects.create(
            point_vente=self.restaurant,
            code="SALLE",
            nom="Salle principale",
            actif=True,
        )
        self.other_salle = SalleModel.objects.create(
            point_vente=self.other_restaurant,
            code="SALLE",
            nom="Salle B",
            actif=True,
        )
        self.table = TableModel.objects.create(
            salle=self.salle,
            numero="T1",
            capacite=4,
            actif=True,
        )
        self.other_table = TableModel.objects.create(
            salle=self.other_salle,
            numero="T1",
            capacite=4,
            actif=True,
        )

        self.server_user = User.objects.create_user(username="serveur-v1")
        self.server = Employe.objects.create(
            user=self.server_user,
            nom="Traore",
            prenom="Awa",
            actif=True,
        )
        AffectationPointVente.objects.create(
            employe=self.server,
            point_vente=self.restaurant,
            role=RolePOS.SERVEUR,
            mode_acces=ModeAccesPOS.PERMANENT,
            actif=True,
            peut_vendre=True,
            peut_gerer_salle=True,
            peut_servir_commande=True,
        )

        self.kitchen_user = User.objects.create_user(username="cuisine-v1")
        self.kitchen = Employe.objects.create(
            user=self.kitchen_user,
            nom="Diallo",
            prenom="Moussa",
            actif=True,
        )
        AffectationPointVente.objects.create(
            employe=self.kitchen,
            point_vente=self.restaurant,
            role=RolePOS.PREPARATEUR,
            mode_acces=ModeAccesPOS.PERMANENT,
            actif=True,
            peut_gerer_cuisine=True,
        )

    def command(self, **kwargs):
        defaults = {
            "point_vente": self.restaurant,
            "type_commande": "SUR_PLACE",
            "created_by": self.server,
            "statut": "EN_ATTENTE",
        }
        defaults.update(kwargs)
        return Commande.objects.create(**defaults)

    def test_server_can_occupy_and_bind_table(self):
        RestaurantService.occuper_table(
            table=self.table,
            employe=self.server,
            user=self.server_user,
            nombre_couverts=3,
        )
        commande = self.command()

        RestaurantService.lier_commande_table(
            commande=commande,
            table=self.table,
            employe=self.server,
            user=self.server_user,
            nombre_couverts=3,
        )

        commande.refresh_from_db()
        self.table.refresh_from_db()
        self.assertEqual(commande.table_id, self.table.id)
        self.assertEqual(self.table.statut, "COMMANDE_EN_COURS")
        self.assertEqual(self.table.serveur_actuel_id, self.server.id)
        self.assertEqual(self.table.nombre_couverts, 3)

    def test_table_cannot_have_two_active_orders(self):
        first = self.command()
        RestaurantService.lier_commande_table(
            commande=first,
            table=self.table,
            employe=self.server,
            user=self.server_user,
        )

        second = self.command()
        with self.assertRaisesMessage(
            RestaurantWorkflowError,
            "déjà utilisée",
        ):
            RestaurantService.lier_commande_table(
                commande=second,
                table=self.table,
                employe=self.server,
                user=self.server_user,
            )

    def test_table_from_other_restaurant_is_rejected(self):
        commande = self.command()
        with self.assertRaisesMessage(
            RestaurantWorkflowError,
            "n'appartient pas",
        ):
            RestaurantService.lier_commande_table(
                commande=commande,
                table=self.other_table,
                employe=self.server,
                user=self.server_user,
            )

    @patch(
        "apps.restaurant.services.restaurant_service."
        "RestaurantConsumptionService.consommer_commande"
    )
    @patch(
        "apps.restaurant.services.restaurant_service."
        "RestaurantConsumptionService.verifier_disponibilite_commande",
        return_value={"disponible": True, "manques": []},
    )
    def test_kitchen_then_server_service_flow(self, _verify, _consume):
        commande = self.command()
        RestaurantService.lier_commande_table(
            commande=commande,
            table=self.table,
            employe=self.server,
            user=self.server_user,
        )

        commande = RestaurantService.demarrer_preparation(
            commande=commande,
            user=self.kitchen_user,
        )
        self.assertEqual(commande.statut, "EN_PREPARATION")

        commande = RestaurantService.marquer_prete(
            commande=commande,
            user=self.kitchen_user,
        )
        self.assertEqual(commande.statut, "PRETE")

        commande = RestaurantService.servir(
            commande=commande,
            user=self.server_user,
        )
        self.assertEqual(commande.statut, "SERVIE")

        self.table.refresh_from_db()
        self.assertEqual(self.table.statut, "A_ENCAISSER")
        _consume.assert_called_once()

    @patch(
        "apps.restaurant.services.restaurant_service."
        "RestaurantConsumptionService.consommer_commande"
    )
    @patch(
        "apps.restaurant.services.restaurant_service."
        "RestaurantConsumptionService.verifier_disponibilite_commande",
        return_value={"disponible": True, "manques": []},
    )
    def test_server_cannot_start_kitchen_preparation(self, _verify, _consume):
        commande = self.command()

        with self.assertRaisesMessage(
            RestaurantWorkflowError,
            "Action Restaurant refusée",
        ):
            RestaurantService.demarrer_preparation(
                commande=commande,
                user=self.server_user,
            )

        commande.refresh_from_db()
        self.assertEqual(commande.statut, "EN_ATTENTE")
        _consume.assert_not_called()

    def test_kitchen_cannot_serve_order(self):
        commande = self.command(statut="PRETE")
        RestaurantService.lier_commande_table(
            commande=commande,
            table=self.table,
            employe=self.server,
            user=self.server_user,
        )

        with self.assertRaisesMessage(
            RestaurantWorkflowError,
            "Action Restaurant refusée",
        ):
            RestaurantService.servir(
                commande=commande,
                user=self.kitchen_user,
            )

    def test_paid_order_frees_table(self):
        commande = self.command(statut="SERVIE")
        RestaurantService.lier_commande_table(
            commande=commande,
            table=self.table,
            employe=self.server,
            user=self.server_user,
        )
        self.table.statut = "A_ENCAISSER"
        self.table.save(update_fields=["statut"])

        commande.statut = "PAYEE"
        commande.save(update_fields=["statut"])
        RestaurantService.liberer_table_si_terminee(commande)

        self.table.refresh_from_db()
        self.assertEqual(self.table.statut, "LIBRE")
        self.assertIsNone(self.table.serveur_actuel_id)
        self.assertEqual(self.table.nombre_couverts, 0)

    def test_table_capacity_is_enforced(self):
        commande = self.command()
        with self.assertRaisesMessage(
            RestaurantWorkflowError,
            "capacité maximale",
        ):
            RestaurantService.lier_commande_table(
                commande=commande,
                table=self.table,
                employe=self.server,
                user=self.server_user,
                nombre_couverts=5,
            )

    def test_restaurant_table_order_cannot_be_paid_before_service(self):
        commande = self.command(statut="EN_ATTENTE")
        RestaurantService.lier_commande_table(
            commande=commande,
            table=self.table,
            employe=self.server,
            user=self.server_user,
        )

        with self.assertRaisesMessage(
            CommandeSettlementError,
            "doit être servie",
        ):
            CommandeSettlementService.regler(
                commande=commande,
                utilisateur=self.server_user,
                mode_paiement="ESPECES",
            )

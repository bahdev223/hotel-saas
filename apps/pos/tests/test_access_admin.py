import json
from datetime import time

from django.contrib.auth.models import Group, User
from django.test import Client, TestCase
from django.urls import reverse

from apps.authentication.groups import MANAGER, PATRON
from apps.pos.constants import ModeAccesPOS, RolePOS, TypePointVente
from apps.pos.models import AffectationPointVente, HoraireAffectation, PointVente
from apps.rh.models import Employe


class POSAccessAdminTests(TestCase):
    def setUp(self):
        self.client = Client()

        self.manager_user = User.objects.create_user(
            username="manager-pos",
            password="pass",
        )
        manager_group, _ = Group.objects.get_or_create(name=MANAGER)
        self.manager_user.groups.add(manager_group)
        Employe.objects.create(
            user=self.manager_user,
            nom="Manager",
            prenom="POS",
            actif=True,
        )

        self.patron_user = User.objects.create_user(
            username="patron-pos",
            password="pass",
        )
        patron_group, _ = Group.objects.get_or_create(name=PATRON)
        self.patron_user.groups.add(patron_group)
        Employe.objects.create(
            user=self.patron_user,
            nom="Patron",
            prenom="POS",
            actif=True,
        )

        self.staff_user = User.objects.create_user(username="staff-pos")
        self.staff = Employe.objects.create(
            user=self.staff_user,
            nom="Traore",
            prenom="Moussa",
            actif=True,
        )

        self.bar = PointVente.objects.create(
            code="BAR-ACCESS",
            nom="Bar principal",
            type=TypePointVente.BAR,
            actif=True,
        )
        self.restaurant = PointVente.objects.create(
            code="RESTO-ACCESS",
            nom="Restaurant",
            type=TypePointVente.RESTAURATION,
            actif=True,
        )

    def _login_manager(self):
        self.client.force_login(self.manager_user)

    def _payload(self, **overrides):
        data = {
            "employe_id": self.staff.id,
            "point_vente_id": self.bar.id,
            "role": RolePOS.SERVEUR,
            "mode_acces": ModeAccesPOS.PLANNING,
            "actif": True,
            "principal": False,
            "permissions": {
                "peut_vendre": True,
                "peut_encaisser": False,
                "peut_ouvrir_caisse": False,
                "peut_fermer_caisse": False,
                "peut_annuler_vente": False,
                "peut_accorder_remise": False,
                "peut_consulter_rapports": False,
            },
        }
        data.update(overrides)
        return data

    def test_manager_can_create_scoped_assignment(self):
        self._login_manager()
        response = self.client.post(
            reverse("pos:api_affectation_enregistrer"),
            data=json.dumps(self._payload()),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["success"])

        affectation = AffectationPointVente.objects.get(
            employe=self.staff,
            point_vente=self.bar,
        )
        self.assertEqual(affectation.mode_acces, ModeAccesPOS.PLANNING)
        self.assertTrue(affectation.peut_vendre)
        self.assertFalse(affectation.peut_encaisser)

    def test_manager_cannot_grant_total_but_patron_can(self):
        self._login_manager()
        response = self.client.post(
            reverse("pos:api_affectation_enregistrer"),
            data=json.dumps(self._payload(mode_acces=ModeAccesPOS.TOTAL)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 403)

        self.client.force_login(self.patron_user)
        response = self.client.post(
            reverse("pos:api_affectation_enregistrer"),
            data=json.dumps(self._payload(mode_acces=ModeAccesPOS.TOTAL)),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            AffectationPointVente.objects.get(employe=self.staff).mode_acces,
            ModeAccesPOS.TOTAL,
        )

    def test_replacing_hours_activates_hours_mode(self):
        self._login_manager()
        affectation = AffectationPointVente.objects.create(
            employe=self.staff,
            point_vente=self.bar,
            role=RolePOS.SERVEUR,
            mode_acces=ModeAccesPOS.PERMANENT,
            actif=True,
            peut_vendre=True,
        )

        response = self.client.post(
            reverse("pos:api_horaires_remplacer", args=[affectation.id]),
            data=json.dumps({
                "activer_mode_horaires": True,
                "horaires": [{
                    "jour_semaine": 0,
                    "heure_debut": "08:00",
                    "heure_fin": "18:00",
                    "actif": True,
                }],
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        affectation.refresh_from_db()
        self.assertEqual(affectation.mode_acces, ModeAccesPOS.HORAIRES)
        self.assertEqual(affectation.horaires.count(), 1)

    def test_hours_conflict_across_bar_and_restaurant_is_rejected(self):
        self._login_manager()

        bar_access = AffectationPointVente.objects.create(
            employe=self.staff,
            point_vente=self.bar,
            role=RolePOS.SERVEUR,
            mode_acces=ModeAccesPOS.HORAIRES,
            actif=True,
            peut_vendre=True,
        )
        HoraireAffectation.objects.create(
            affectation=bar_access,
            jour_semaine=1,
            heure_debut=time(16, 0),
            heure_fin=time(23, 0),
            actif=True,
        )

        resto_access = AffectationPointVente.objects.create(
            employe=self.staff,
            point_vente=self.restaurant,
            role=RolePOS.SERVEUR,
            mode_acces=ModeAccesPOS.HORAIRES,
            actif=True,
            peut_vendre=True,
        )

        response = self.client.post(
            reverse("pos:api_horaires_remplacer", args=[resto_access.id]),
            data=json.dumps({
                "horaires": [{
                    "jour_semaine": 1,
                    "heure_debut": "18:00",
                    "heure_fin": "22:00",
                    "actif": True,
                }],
            }),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 409)
        self.assertIn("Conflit", response.json()["error"])

    def test_access_list_is_bar_restaurant_only(self):
        legacy = PointVente.objects.create(
            code="RECEP-LEGACY",
            nom="Réception legacy",
            type=TypePointVente.RECEPTION,
            actif=True,
        )
        AffectationPointVente.objects.create(
            employe=self.staff,
            point_vente=legacy,
            role=RolePOS.CAISSIER,
            actif=True,
        )
        AffectationPointVente.objects.create(
            employe=self.staff,
            point_vente=self.bar,
            role=RolePOS.SERVEUR,
            actif=True,
        )

        self._login_manager()
        response = self.client.get(reverse("pos:api_acces_liste"))
        self.assertEqual(response.status_code, 200)
        points = {
            item["point_vente"]["type"]
            for item in response.json()["affectations"]
        }
        self.assertEqual(points, {TypePointVente.BAR})

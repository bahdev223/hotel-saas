import json
from datetime import time

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from apps.authentication.groups import MANAGER, PATRON
from apps.pos.constants import ModeAccesPOS, TypePointVente
from apps.pos.models import AffectationPointVente, HoraireAffectation, PointVente
from apps.rh.models import Employe


class POSAccessAdminAPITests(TestCase):
    def setUp(self):
        self.manager_user = User.objects.create_user(username="manager")
        self.manager_group = Group.objects.create(name=MANAGER)
        self.manager_user.groups.add(self.manager_group)

        self.patron_user = User.objects.create_user(username="patron")
        self.patron_group = Group.objects.create(name=PATRON)
        self.patron_user.groups.add(self.patron_group)

        self.employee_user = User.objects.create_user(username="amadou")
        self.employe = Employe.objects.create(
            user=self.employee_user,
            nom="Traore",
            prenom="Amadou",
            actif=True,
        )
        self.bar = PointVente.objects.create(
            code="BAR-API",
            nom="Bar API",
            type=TypePointVente.BAR,
            actif=True,
        )
        self.restaurant = PointVente.objects.create(
            code="RESTO-API",
            nom="Restaurant API",
            type=TypePointVente.RESTAURATION,
            actif=True,
        )

    def post_json(self, url, payload):
        return self.client.post(
            url,
            data=json.dumps(payload),
            content_type="application/json",
        )

    def test_manager_creates_cashier_with_role_preset(self):
        self.client.force_login(self.manager_user)
        response = self.post_json(
            reverse("pos:api_affectation_enregistrer"),
            {
                "employe_id": self.employe.id,
                "point_vente_id": self.bar.id,
                "role": "CAISSIER",
                "mode_acces": "PERMANENT",
                "appliquer_preset": True,
            },
        )
        self.assertEqual(response.status_code, 200, response.content)

        affectation = AffectationPointVente.objects.get(
            employe=self.employe,
            point_vente=self.bar,
        )
        self.assertTrue(affectation.peut_vendre)
        self.assertTrue(affectation.peut_encaisser)
        self.assertTrue(affectation.peut_ouvrir_caisse)
        self.assertTrue(affectation.peut_fermer_caisse)
        self.assertFalse(affectation.peut_annuler_vente)

    def test_manager_cannot_grant_total_access(self):
        self.client.force_login(self.manager_user)
        response = self.post_json(
            reverse("pos:api_affectation_enregistrer"),
            {
                "employe_id": self.employe.id,
                "point_vente_id": self.bar.id,
                "role": "RESPONSABLE",
                "mode_acces": "TOTAL",
                "appliquer_preset": True,
            },
        )
        self.assertEqual(response.status_code, 403)
        self.assertFalse(
            AffectationPointVente.objects.filter(
                employe=self.employe,
                mode_acces=ModeAccesPOS.TOTAL,
            ).exists()
        )

    def test_patron_can_grant_single_total_access(self):
        self.client.force_login(self.patron_user)
        url = reverse("pos:api_affectation_enregistrer")

        first = self.post_json(url, {
            "employe_id": self.employe.id,
            "point_vente_id": self.bar.id,
            "role": "RESPONSABLE",
            "mode_acces": "TOTAL",
            "appliquer_preset": True,
        })
        self.assertEqual(first.status_code, 200, first.content)

        duplicate = self.post_json(url, {
            "employe_id": self.employe.id,
            "point_vente_id": self.restaurant.id,
            "role": "SUPERVISEUR",
            "mode_acces": "TOTAL",
            "appliquer_preset": True,
        })
        self.assertEqual(duplicate.status_code, 409)

    def test_replacing_hours_rejects_overlap_without_destroying_existing(self):
        self.client.force_login(self.manager_user)
        affectation = AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=self.bar,
            role="CAISSIER",
            mode_acces=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
            peut_encaisser=True,
            actif=True,
        )
        url = reverse(
            "pos:api_horaires_remplacer",
            kwargs={"affectation_id": affectation.id},
        )

        valid = self.post_json(url, {
            "horaires": [
                {
                    "jour_semaine": 0,
                    "heure_debut": "08:00",
                    "heure_fin": "12:00",
                    "actif": True,
                },
                {
                    "jour_semaine": 0,
                    "heure_debut": "13:00",
                    "heure_fin": "18:00",
                    "actif": True,
                },
            ],
        })
        self.assertEqual(valid.status_code, 200, valid.content)
        self.assertEqual(
            HoraireAffectation.objects.filter(affectation=affectation).count(),
            2,
        )

        invalid = self.post_json(url, {
            "horaires": [
                {
                    "jour_semaine": 0,
                    "heure_debut": "08:00",
                    "heure_fin": "14:00",
                    "actif": True,
                },
                {
                    "jour_semaine": 0,
                    "heure_debut": "13:00",
                    "heure_fin": "18:00",
                    "actif": True,
                },
            ],
        })
        self.assertEqual(invalid.status_code, 400)
        self.assertEqual(
            list(
                HoraireAffectation.objects.filter(affectation=affectation)
                .order_by("heure_debut")
                .values_list("heure_debut", "heure_fin")
            ),
            [
                (time(8, 0), time(12, 0)),
                (time(13, 0), time(18, 0)),
            ],
        )

    def test_recurring_hours_conflict_across_bar_and_restaurant(self):
        self.client.force_login(self.manager_user)
        bar_access = AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=self.bar,
            role="SERVEUR",
            mode_acces=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
            actif=True,
        )
        restaurant_access = AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=self.restaurant,
            role="SERVEUR",
            mode_acces=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
            actif=True,
        )

        bar_url = reverse(
            "pos:api_horaires_remplacer",
            kwargs={"affectation_id": bar_access.id},
        )
        restaurant_url = reverse(
            "pos:api_horaires_remplacer",
            kwargs={"affectation_id": restaurant_access.id},
        )

        first = self.post_json(bar_url, {
            "horaires": [{
                "jour_semaine": 0,
                "heure_debut": "18:00",
                "heure_fin": "23:00",
            }],
        })
        self.assertEqual(first.status_code, 200, first.content)

        conflict = self.post_json(restaurant_url, {
            "horaires": [{
                "jour_semaine": 0,
                "heure_debut": "20:00",
                "heure_fin": "23:30",
            }],
        })
        self.assertEqual(conflict.status_code, 409)
        self.assertIn("Bar API", conflict.json()["error"])
        self.assertFalse(
            HoraireAffectation.objects.filter(
                affectation=restaurant_access
            ).exists()
        )

    def test_zero_length_recurring_hour_is_rejected(self):
        self.client.force_login(self.manager_user)
        affectation = AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=self.bar,
            role="SERVEUR",
            mode_acces=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
            actif=True,
        )
        response = self.post_json(
            reverse(
                "pos:api_horaires_remplacer",
                kwargs={"affectation_id": affectation.id},
            ),
            {
                "horaires": [{
                    "jour_semaine": 1,
                    "heure_debut": "08:00",
                    "heure_fin": "08:00",
                }],
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(
            HoraireAffectation.objects.filter(affectation=affectation).exists()
        )

    def test_access_list_exposes_only_bar_restaurant_assignments(self):
        reception = PointVente.objects.create(
            code="REC-LEGACY",
            nom="Reception Legacy",
            type=TypePointVente.RECEPTION,
            actif=True,
        )
        AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=reception,
            role="CAISSIER",
            actif=True,
        )
        AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=self.bar,
            role="CAISSIER",
            actif=True,
        )

        self.client.force_login(self.manager_user)
        response = self.client.get(reverse("pos:api_acces_liste"))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["affectations"]), 1)
        self.assertEqual(
            payload["affectations"][0]["point_vente"]["type"],
            TypePointVente.BAR,
        )

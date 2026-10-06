from datetime import datetime, time

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.utils import timezone

from apps.authentication.groups import MANAGER
from apps.pos.constants import ActionPOS, ModeAccesPOS, TypePointVente
from apps.pos.models import (
    AffectationPointVente,
    HoraireAffectation,
    PointVente,
    ShiftEmploye,
)
from apps.pos.services.access_service import POSAccessService
from apps.rh.models import Employe


class POSAccessServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="moussa")
        self.employe = Employe.objects.create(
            user=self.user,
            nom="Traore",
            prenom="Moussa",
            actif=True,
        )
        self.bar = PointVente.objects.create(
            code="BAR-1",
            nom="Bar",
            type=TypePointVente.BAR,
            actif=True,
        )
        self.restaurant = PointVente.objects.create(
            code="RESTO-1",
            nom="Restaurant",
            type=TypePointVente.RESTAURATION,
            actif=True,
        )
        self.reception = PointVente.objects.create(
            code="REC-1",
            nom="Reception legacy",
            type=TypePointVente.RECEPTION,
            actif=True,
        )

    @staticmethod
    def at(year, month, day, hour, minute=0):
        return timezone.make_aware(datetime(year, month, day, hour, minute))

    def affectation(self, point=None, mode=ModeAccesPOS.PERMANENT, **permissions):
        defaults = {
            "peut_vendre": False,
            "peut_encaisser": False,
            "peut_ouvrir_caisse": False,
            "peut_fermer_caisse": False,
            "peut_annuler_vente": False,
            "peut_accorder_remise": False,
            "peut_consulter_rapports": False,
        }
        defaults.update(permissions)
        return AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=point or self.bar,
            mode_acces=mode,
            actif=True,
            **defaults,
        )

    def test_scope_is_strictly_bar_and_restaurant(self):
        self.affectation(self.reception, peut_vendre=True)
        decision = POSAccessService.check(
            user=self.user,
            point_vente=self.reception,
            action=ActionPOS.VENDRE,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(
            decision.reason,
            "HORS_PERIMETRE_POS_BAR_RESTAURANT",
        )

    def test_permanent_assignment_is_point_specific(self):
        self.affectation(self.bar, peut_vendre=True)

        self.assertTrue(POSAccessService.can(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.VENDRE,
        ))
        self.assertFalse(POSAccessService.can(
            user=self.user,
            point_vente=self.restaurant,
            action=ActionPOS.VENDRE,
        ))

    def test_permission_is_separate_from_access(self):
        self.affectation(
            self.bar,
            peut_vendre=True,
            peut_encaisser=False,
        )

        self.assertTrue(POSAccessService.can(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.VENDRE,
        ))
        decision = POSAccessService.check(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.ENCAISSER,
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "PERMISSION_METIER_REFUSEE")

    def test_recurring_hours_allow_only_current_window(self):
        affectation = self.affectation(
            self.bar,
            mode=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
        )
        HoraireAffectation.objects.create(
            affectation=affectation,
            jour_semaine=0,
            heure_debut=time(8, 0),
            heure_fin=time(18, 0),
        )

        self.assertTrue(POSAccessService.can(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.VENDRE,
            moment=self.at(2026, 10, 5, 10, 0),
        ))
        self.assertFalse(POSAccessService.can(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.VENDRE,
            moment=self.at(2026, 10, 5, 19, 0),
        ))

    def test_overnight_hours_continue_after_midnight(self):
        affectation = self.affectation(
            self.bar,
            mode=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
        )
        HoraireAffectation.objects.create(
            affectation=affectation,
            jour_semaine=4,
            heure_debut=time(18, 0),
            heure_fin=time(2, 0),
        )

        self.assertTrue(POSAccessService.can(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.VENDRE,
            moment=self.at(2026, 10, 10, 1, 0),
        ))

    def test_dated_overnight_window_remains_valid_after_midnight(self):
        affectation = self.affectation(
            self.bar,
            mode=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
        )
        HoraireAffectation.objects.create(
            affectation=affectation,
            jour_semaine=4,
            heure_debut=time(18, 0),
            heure_fin=time(2, 0),
            date_debut=self.at(2026, 10, 9, 0, 0).date(),
            date_fin=self.at(2026, 10, 9, 0, 0).date(),
        )

        self.assertTrue(POSAccessService.can(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.VENDRE,
            moment=self.at(2026, 10, 10, 1, 0),
        ))
        self.assertFalse(POSAccessService.can(
            user=self.user,
            point_vente=self.bar,
            action=ActionPOS.VENDRE,
            moment=self.at(2026, 10, 10, 3, 0),
        ))

    def test_planning_requires_active_shift(self):
        affectation = self.affectation(
            self.restaurant,
            mode=ModeAccesPOS.PLANNING,
            peut_vendre=True,
        )
        now = self.at(2026, 10, 6, 19, 0)

        self.assertFalse(POSAccessService.can(
            user=self.user,
            point_vente=self.restaurant,
            action=ActionPOS.VENDRE,
            moment=now,
        ))

        shift = ShiftEmploye.objects.create(
            affectation=affectation,
            debut_prevu=self.at(2026, 10, 6, 18, 0),
            fin_prevue=self.at(2026, 10, 6, 23, 0),
            statut="CONFIRME",
            cree_par=self.user,
        )

        decision = POSAccessService.check(
            user=self.user,
            point_vente=self.restaurant,
            action=ActionPOS.VENDRE,
            moment=now,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.mode, ModeAccesPOS.PLANNING)
        self.assertEqual(decision.shift_id, shift.id)

    def test_explicit_total_assignment_applies_to_all_operational_points(self):
        self.affectation(
            self.bar,
            mode=ModeAccesPOS.TOTAL,
            peut_encaisser=True,
        )
        self.assertTrue(POSAccessService.can(
            user=self.user,
            point_vente=self.restaurant,
            action=ActionPOS.ENCAISSER,
        ))

    def test_manager_has_total_access_without_assignment(self):
        manager, _ = Group.objects.get_or_create(name=MANAGER)
        self.user.groups.add(manager)

        decision = POSAccessService.check(
            user=self.user,
            point_vente=self.restaurant,
            action=ActionPOS.OUVRIR_CAISSE,
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.mode, ModeAccesPOS.TOTAL)

from datetime import datetime, time

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.core.models import JourneeExploitation
from apps.pos.constants import ModeAccesPOS, TypePointVente
from apps.pos.management.commands.verifier_sessions import Command
from apps.pos.models import (
    AffectationPointVente,
    HoraireAffectation,
    PointVente,
    SessionCaisse,
)
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse


class SessionVerifierAccessTests(TestCase):
    def setUp(self):
        JourneeExploitation.objects.create(
            date_metier=timezone.localdate(),
        )
        self.user = User.objects.create_user(username="caissier-expire")
        self.employe = Employe.objects.create(
            user=self.user,
            nom="Caissier",
            prenom="Test",
            actif=True,
        )
        self.point = PointVente.objects.create(
            code="BAR-VERIFY",
            nom="Bar Verify",
            type=TypePointVente.BAR,
            actif=True,
        )
        self.caisse = Caisse.objects.create(
            code="C-VERIFY",
            nom="Caisse Verify",
            actif=True,
        )
        self.session = SessionCaisse.objects.create(
            caisse=self.caisse,
            point_vente=self.point,
            ouverte_par=self.employe,
            statut="OUVERTE",
        )

    @staticmethod
    def at(year, month, day, hour, minute=0):
        return timezone.make_aware(datetime(year, month, day, hour, minute))

    def command(self):
        cmd = Command()
        cmd.fix = True
        cmd.dry_run = False
        cmd.anomalies = []
        cmd.corrections = []
        return cmd

    def test_expired_hours_move_open_session_to_handover(self):
        affectation = AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=self.point,
            role="CAISSIER",
            mode_acces=ModeAccesPOS.HORAIRES,
            peut_vendre=True,
            peut_encaisser=True,
            peut_ouvrir_caisse=True,
            peut_fermer_caisse=True,
            actif=True,
        )
        HoraireAffectation.objects.create(
            affectation=affectation,
            jour_semaine=0,
            heure_debut=time(8, 0),
            heure_fin=time(9, 0),
        )

        cmd = self.command()
        cmd._checker_acces_expire(self.at(2026, 10, 5, 10, 0))

        self.session.refresh_from_db()
        self.assertEqual(self.session.statut, "EN_PASSATION")
        self.assertIsNotNone(self.session.date_passation)
        self.assertIsNotNone(self.session.passation_jusqua)
        self.assertEqual(len(cmd.anomalies), 1)
        self.assertTrue(cmd.anomalies[0]["corrigee"])
        self.assertEqual(cmd.anomalies[0]["type"], "ACCES_CAISSE_EXPIRE")
        self.assertIn("HORS_CRENEAU_AUTORISE", self.session.motif_passation)

    def test_permanent_access_keeps_session_open(self):
        AffectationPointVente.objects.create(
            employe=self.employe,
            point_vente=self.point,
            role="CAISSIER",
            mode_acces=ModeAccesPOS.PERMANENT,
            peut_vendre=True,
            peut_encaisser=True,
            peut_ouvrir_caisse=True,
            peut_fermer_caisse=True,
            actif=True,
        )

        cmd = self.command()
        cmd._checker_acces_expire(self.at(2026, 10, 5, 10, 0))

        self.session.refresh_from_db()
        self.assertEqual(self.session.statut, "OUVERTE")
        self.assertEqual(cmd.anomalies, [])

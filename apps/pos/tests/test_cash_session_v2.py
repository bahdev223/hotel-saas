from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

from django.contrib.auth.models import User
from django.test import TestCase
from django.utils import timezone

from apps.pos.constants import ModeAccesPOS, RolePOS, TypePointVente
from apps.pos.models import (
    AffectationPointVente,
    CaissePointVente,
    PointVente,
    SessionCaisse,
    Vente,
)
from apps.pos.services.caisse_session_service import CaisseSessionService
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse


class CashSessionV2Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier-v2")
        self.cashier = Employe.objects.create(
            user=self.user,
            nom="Traore",
            prenom="Awa",
            actif=True,
        )
        self.other_user = User.objects.create_user(username="other-cashier-v2")
        self.other_cashier = Employe.objects.create(
            user=self.other_user,
            nom="Diallo",
            prenom="Moussa",
            actif=True,
        )
        self.pv = PointVente.objects.create(
            code="BAR-CASH-V2",
            nom="Bar principal",
            type=TypePointVente.BAR,
            actif=True,
            delai_passation_minutes=15,
        )
        self.caisse = Caisse.objects.create(
            code="CASH-V2",
            nom="Caisse Bar",
            role="POINT_VENTE",
            solde=Decimal("10000"),
            actif=True,
        )
        CaissePointVente.objects.create(
            point_vente=self.pv,
            caisse=self.caisse,
            principale=True,
            actif=True,
        )
        self.assignment = AffectationPointVente.objects.create(
            employe=self.cashier,
            point_vente=self.pv,
            role=RolePOS.CAISSIER,
            mode_acces=ModeAccesPOS.PERMANENT,
            actif=True,
            principal=True,
            peut_vendre=True,
            peut_encaisser=True,
            peut_ouvrir_caisse=True,
            peut_fermer_caisse=True,
        )
        AffectationPointVente.objects.create(
            employe=self.other_cashier,
            point_vente=self.pv,
            role=RolePOS.CAISSIER,
            mode_acces=ModeAccesPOS.PERMANENT,
            actif=True,
            peut_vendre=True,
            peut_encaisser=True,
            peut_ouvrir_caisse=True,
            peut_fermer_caisse=True,
        )

    def open_session(self):
        return CaisseSessionService.ouverture_session(
            caisse=self.caisse,
            point_vente=self.pv,
            caissier=self.cashier,
        )

    def test_opening_snapshots_access_authority(self):
        session = self.open_session()

        self.assertEqual(session.mode_acces_ouverture, ModeAccesPOS.PERMANENT)
        self.assertEqual(session.raison_acces_ouverture, "ACCES_PERMANENT")
        self.assertEqual(
            session.affectation_ouverture_id,
            self.assignment.id,
        )
        self.assertTrue(session.permissions_ouverture["peut_encaisser"])
        self.assertTrue(session.permissions_ouverture["peut_ouvrir_caisse"])

    def test_only_one_non_finalized_session_per_cash_register(self):
        self.open_session()

        with self.assertRaises(ValueError):
            CaisseSessionService.ouverture_session(
                caisse=self.caisse,
                point_vente=self.pv,
                caissier=self.other_cashier,
            )

    def test_session_financial_ownership_is_strict(self):
        session = self.open_session()

        allowed, reason = CaisseSessionService.autoriser_encaissement_session(
            session=session,
            encaisseur=self.other_cashier,
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "SESSION_APPARTIENT_A_UN_AUTRE_CAISSIER")

    def test_handover_has_grace_window_for_existing_order(self):
        session = self.open_session()
        now = timezone.now()
        session = CaisseSessionService.demarrer_passation(
            session,
            motif="Fin de shift",
            moment=now,
        )

        existing_order = SimpleNamespace(date_commande=now - timedelta(minutes=5))
        allowed, reason = CaisseSessionService.autoriser_encaissement_session(
            session=session,
            encaisseur=self.cashier,
            commande=existing_order,
            moment=now + timedelta(minutes=5),
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "PASSATION_GRACE_ACTIVE")

        new_order = SimpleNamespace(date_commande=now + timedelta(minutes=1))
        allowed, reason = CaisseSessionService.autoriser_encaissement_session(
            session=session,
            encaisseur=self.cashier,
            commande=new_order,
            moment=now + timedelta(minutes=5),
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "COMMANDE_APRES_PASSATION")

    def test_handover_grace_expires(self):
        session = self.open_session()
        now = timezone.now()
        session = CaisseSessionService.demarrer_passation(
            session,
            motif="Fin de shift",
            moment=now,
        )

        allowed, reason = CaisseSessionService.autoriser_encaissement_session(
            session=session,
            encaisseur=self.cashier,
            commande=SimpleNamespace(date_commande=now - timedelta(minutes=1)),
            moment=now + timedelta(minutes=16),
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "PASSATION_EXPIREE")

    def test_counting_expected_cash_includes_opening_float(self):
        session = self.open_session()
        Vente.objects.create(
            point_vente=self.pv,
            caisse=self.caisse,
            session_caisse=session,
            caissier=self.cashier,
            encaisse_par=self.cashier,
            numero="V-CASH-V2-1",
            sous_total=Decimal("2000"),
            montant_total=Decimal("2000"),
            montant_paye=Decimal("2000"),
            mode_paiement="ESPECES",
            statut="PAYEE",
        )

        result = CaisseSessionService.fermeture_session(
            session=session,
            especes_comptees=Decimal("12000"),
            fermee_par=self.cashier,
        )

        self.assertEqual(result["especes_attendues"], Decimal("12000"))
        self.assertEqual(result["ecart_especes"], Decimal("0"))
        self.assertEqual(result["ecart"], Decimal("0"))

        session.refresh_from_db()
        self.assertEqual(session.statut, "FERMEE")
        self.assertEqual(session.comptage.ecart_total, Decimal("0"))

    def test_large_gap_requires_reason(self):
        session = self.open_session()

        with self.assertRaisesMessage(
            ValueError,
            "Un motif est obligatoire",
        ):
            CaisseSessionService.fermeture_session(
                session=session,
                especes_comptees=Decimal("0"),
                fermee_par=self.cashier,
                notes="",
            )

    def test_closed_session_can_be_validated(self):
        session = self.open_session()
        CaisseSessionService.fermeture_session(
            session=session,
            especes_comptees=Decimal("10000"),
            fermee_par=self.cashier,
        )
        session.refresh_from_db()

        validated = CaisseSessionService.valider_session(
            session,
            self.cashier,
        )

        self.assertEqual(validated.statut, "VALIDEE")
        self.assertEqual(validated.validee_par_id, self.cashier.id)
        self.assertIsNotNone(validated.date_validation)

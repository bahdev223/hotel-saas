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
    ShiftEmploye,
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
        self.assertEqual(session.solde_attendu, Decimal("12000"))
        self.assertEqual(session.solde_reel, Decimal("12000"))
        self.assertEqual(session.difference, Decimal("0"))

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

    def test_handover_blocks_new_session_until_finalized(self):
        session = self.open_session()
        CaisseSessionService.demarrer_passation(
            session,
            motif="Passation",
        )

        with self.assertRaises(ValueError):
            CaisseSessionService.ouverture_session(
                caisse=self.caisse,
                point_vente=self.pv,
                caissier=self.other_cashier,
            )

    def test_handover_uses_immutable_opening_permissions(self):
        session = self.open_session()

        self.assignment.peut_encaisser = False
        self.assignment.peut_fermer_caisse = False
        self.assignment.actif = False
        self.assignment.save(update_fields=[
            "peut_encaisser",
            "peut_fermer_caisse",
            "actif",
        ])

        now = timezone.now()
        session = CaisseSessionService.demarrer_passation(
            session,
            motif="Droits modifiés après ouverture",
            moment=now,
        )
        existing_order = SimpleNamespace(
            date_commande=now - timedelta(minutes=1),
        )

        allowed, reason = CaisseSessionService.autoriser_encaissement_session(
            session=session,
            encaisseur=self.cashier,
            commande=existing_order,
            moment=now + timedelta(minutes=1),
        )
        self.assertTrue(allowed)
        self.assertEqual(reason, "PASSATION_GRACE_ACTIVE")

        can_close, close_reason = (
            CaisseSessionService.autoriser_finalisation_session(
                session,
                self.cashier,
            )
        )
        self.assertTrue(can_close)
        self.assertEqual(close_reason, "SNAPSHOT_FERMETURE_AUTORISEE")

    def test_inactive_employee_cannot_use_handover_grace(self):
        session = self.open_session()
        now = timezone.now()
        session = CaisseSessionService.demarrer_passation(
            session,
            motif="Fin de service",
            moment=now,
        )
        self.cashier.actif = False
        self.cashier.save(update_fields=["actif"])

        allowed, reason = CaisseSessionService.autoriser_encaissement_session(
            session=session,
            encaisseur=self.cashier,
            commande=SimpleNamespace(
                date_commande=now - timedelta(minutes=1),
            ),
            moment=now + timedelta(minutes=1),
        )
        self.assertFalse(allowed)
        self.assertEqual(reason, "EMPLOYE_INACTIF")

    def test_other_cashier_cannot_close_owned_session_via_api(self):
        session = self.open_session()
        self.client.force_login(self.other_user)

        response = self.client.post(
            "/pos/api/sessions/fermer/",
            data={
                "session_id": session.id,
                "especes_comptees": "10000",
            },
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 403)
        session.refresh_from_db()
        self.assertEqual(session.statut, "OUVERTE")

    def test_server_access_does_not_keep_expired_cashier_session_open(self):
        # Même employé : serveur permanent + caissier uniquement sur planning.
        self.assignment.role = RolePOS.SERVEUR
        self.assignment.mode_acces = ModeAccesPOS.PERMANENT
        self.assignment.peut_vendre = True
        self.assignment.peut_encaisser = False
        self.assignment.peut_ouvrir_caisse = False
        self.assignment.peut_fermer_caisse = False
        self.assignment.save()

        cashier_assignment = AffectationPointVente.objects.create(
            employe=self.cashier,
            point_vente=self.pv,
            role=RolePOS.CAISSIER,
            mode_acces=ModeAccesPOS.PLANNING,
            actif=True,
            peut_vendre=True,
            peut_encaisser=True,
            peut_ouvrir_caisse=True,
            peut_fermer_caisse=True,
        )
        now = timezone.now()
        shift = ShiftEmploye.objects.create(
            affectation=cashier_assignment,
            debut_prevu=now - timedelta(hours=1),
            fin_prevue=now + timedelta(hours=1),
            statut="CONFIRME",
            cree_par=self.user,
        )
        session = CaisseSessionService.ouverture_session(
            caisse=self.caisse,
            point_vente=self.pv,
            caissier=self.cashier,
            shift=shift,
        )

        # Le shift caisse finit, mais l'affectation serveur permanente reste.
        shift.fin_prevue = now - timedelta(minutes=1)
        shift.save(update_fields=["fin_prevue"])

        self.client.force_login(self.user)
        response = self.client.get(
            f"/pos/api/sessions/verifier-etat/{self.pv.id}/"
        )

        self.assertEqual(response.status_code, 200)
        session.refresh_from_db()
        self.assertEqual(session.statut, "EN_PASSATION")
        self.assertTrue(response.json()["planning_expire"])

    def test_deposit_cannot_exceed_counted_cash(self):
        session = self.open_session()

        with self.assertRaisesMessage(
            ValueError,
            "Le dépôt ne peut pas dépasser",
        ):
            CaisseSessionService.fermeture_session(
                session=session,
                especes_comptees=Decimal("10000"),
                fermee_par=self.cashier,
                depot=Decimal("11000"),
            )

    def test_negative_reconciliation_amount_is_rejected(self):
        session = self.open_session()

        with self.assertRaisesMessage(
            ValueError,
            "ne peut pas être négatif",
        ):
            CaisseSessionService.fermeture_session(
                session=session,
                especes_comptees=Decimal("-1"),
                fermee_par=self.cashier,
            )

    def test_manual_handover_records_actor(self):
        session = self.open_session()
        session = CaisseSessionService.demarrer_passation(
            session,
            motif="Relève équipe soir",
            par=self.cashier,
        )

        self.assertEqual(session.passation_par_id, self.cashier.id)
        self.assertEqual(session.motif_passation, "Relève équipe soir")


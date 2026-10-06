import json

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.core.models import JourneeExploitation
from apps.pos.constants import ModeAccesPOS, TypePointVente
from apps.pos.models import (
    AffectationPointVente,
    CaissePointVente,
    Commande,
    PointVente,
    PointVenteEntrepot,
    SessionCaisse,
)
from apps.stock.models import Entrepot, Produit, StockEntrepot, UniteMesure
from apps.pos.services.caisse_session_service import CaisseSessionService
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse


class POSOrderScopeTests(TestCase):
    def setUp(self):
        JourneeExploitation.objects.create(date_metier=timezone.localdate())

        self.user = User.objects.create_user(username="serveur-bar", password="pass")
        self.employe = Employe.objects.create(
            user=self.user,
            nom="Serveur",
            prenom="Bar",
            actif=True,
        )
        self.point = PointVente.objects.create(
            code="BAR-SCOPE",
            nom="Bar Scope",
            type=TypePointVente.BAR,
            actif=True,
        )
        self.caisse = Caisse.objects.create(
            code="C-SCOPE",
            nom="Caisse Scope",
            actif=True,
        )
        CaissePointVente.objects.create(
            point_vente=self.point,
            caisse=self.caisse,
            principale=True,
            actif=True,
        )
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
        CaisseSessionService.ouverture_session(
            caisse=self.caisse,
            point_vente=self.point,
            caissier=self.employe,
        )
        self.client.force_login(self.user)

    def post_order(self, lignes):
        return self.client.post(
            reverse("pos:api_creer_commande"),
            data=json.dumps({
                "point_vente_slug": self.point.code,
                "type_commande": "SUR_PLACE",
                "lignes": lignes,
            }),
            content_type="application/json",
        )

    def test_location_is_rejected_without_partial_order(self):
        response = self.post_order([
            {
                "type_article": "LOCATION",
                "unite_id": 999,
                "quantite": 1,
            }
        ])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "HORS_PERIMETRE_POS")
        self.assertEqual(Commande.objects.count(), 0)

    def test_unknown_item_type_is_rejected_without_partial_order(self):
        response = self.post_order([
            {
                "type_article": "CHAMBRE",
                "quantite": 1,
            }
        ])

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["error_code"], "TYPE_ARTICLE_INVALIDE")
        self.assertEqual(Commande.objects.count(), 0)

    def test_server_can_create_order_without_cash_session(self):
        SessionCaisse.objects.all().delete()
        affectation = AffectationPointVente.objects.get(
            employe=self.employe,
            point_vente=self.point,
        )
        affectation.role = "SERVEUR"
        affectation.peut_vendre = True
        affectation.peut_encaisser = False
        affectation.peut_ouvrir_caisse = False
        affectation.peut_fermer_caisse = False
        affectation.save()

        unite, _ = UniteMesure.objects.get_or_create(
            symbole="u",
            defaults={"nom": "Unité", "type_unite": "UNITE"},
        )
        entrepot = Entrepot.objects.create(
            code="BAR-NO-CASH-STOCK",
            nom="Stock Bar sans caisse",
            type_entrepot="BAR",
            actif=True,
        )
        produit = Produit.objects.create(
            code="EAU-NO-CASH",
            nom="Eau",
            prix_achat=100,
            prix_vente=500,
            unite_mesure=unite,
            actif=True,
            est_vendable=True,
        )
        StockEntrepot.objects.create(
            entrepot=entrepot,
            produit=produit,
            quantite=10,
        )
        PointVenteEntrepot.objects.create(
            point_vente=self.point,
            entrepot=entrepot,
            principal=True,
            autorise_vente=True,
            actif=True,
        )

        response = self.post_order([{
            "type_article": "PRODUIT",
            "produit_id": produit.id,
            "quantite": 1,
        }])

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])
        commande = Commande.objects.get(id=response.json()["commande_id"])
        self.assertEqual(commande.created_by_id, self.employe.id)
        self.assertEqual(commande.point_vente_id, self.point.id)
        self.assertEqual(commande.lignes.count(), 1)


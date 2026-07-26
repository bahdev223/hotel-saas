from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from apps.stock.models import Produit, Entrepot, UniteMesure, StockEntrepot
from apps.restaurant.models.recette import RecetteModel, IngredientModel
from apps.pos.models import Commande, LigneCommande, PointVente
from apps.pos.models.caisse_point_vente import CaissePointVente
from apps.pos.services.caisse_session_service import CaisseSessionService
from apps.paiements.services.commande_settlement_service import (
    CommandeSettlementService,
    CommandeSettlementError,
)
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.enums.sources import SourceOperationType
from apps.tresorerie.models import Caisse
from apps.rh.models import Employe


class CommandeSettlementServiceTest(TestCase):
    def setUp(self):
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.farine = Produit.objects.create(code="FARINE", nom="Farine", prix_achat=1000, unite_mesure=self.unite_kg)
        MouvementStockService.entree_stock(self.farine, self.entrepot, 10, "Test", motif=SourceOperationType.ACHAT, valeur_unitaire=1000)

        self.point_vente = PointVente.objects.create(code="PV-TEST", nom="Test", type="RESTAURANT")
        self.caisse = Caisse.objects.create(
            nom="Caisse Test", code="C-TEST", type_financier='ESPECES',
            solde=0, actif=True, point_vente=self.point_vente,
        )
        CaissePointVente.objects.create(caisse=self.caisse, point_vente=self.point_vente, actif=True)

        self.user = User.objects.create_user(username="testuser", password="12345")
        self.employe = Employe.objects.create(
            user=self.user, nom="Test", prenom="User",
        )

        CaisseSessionService.ouverture_session(
            caisse=self.caisse, point_vente=self.point_vente, caissier=self.employe,
        )

        self.commande = Commande.objects.create(
            point_vente=self.point_vente, entrepot=self.entrepot,
            type_commande='SUR_PLACE', montant_total=2000,
        )
        self.recette = RecetteModel.objects.create(
            nom="Gateau", type_recette='DESSERT',
            rendement_quantite=10, rendement_unite_mesure=self.unite_kg,
        )
        IngredientModel.objects.create(
            recette=self.recette, produit=self.farine,
            quantite=1, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE',
        )
        self.ligne = LigneCommande.objects.create(
            commande=self.commande, recette=self.recette,
            quantite=2, prix_unitaire=1000,
        )

    def test_regler_commande_cree_paiement_vente_mouvement(self):
        """Le règlement crée Paiement + Vente + MouvementCaisse + consomme stock"""
        result = CommandeSettlementService.regler(
            commande=self.commande, montant=2000,
            mode_paiement='ESPECES', utilisateur=self.user,
        )

        paiement = result['paiement']
        self.assertEqual(paiement.statut, 'VALIDE')
        self.assertEqual(paiement.montant, Decimal('2000'))
        self.assertEqual(paiement.mode, 'ESPECES')

        vente = result['vente']
        self.assertEqual(vente.statut, 'PAYEE')
        self.assertEqual(vente.montant_total, Decimal('2000'))

        self.commande.refresh_from_db()
        self.assertEqual(self.commande.statut, 'PAYEE')
        self.assertEqual(self.commande.vente_id, vente.id)

        self.caisse.refresh_from_db()
        self.assertGreater(self.caisse.solde, 0)

        # Consommation: 2 portions de Gateau (rendement 10, 1kg farine)
        # Chaque portion consomme 1/10 kg = 0.1 kg, donc 2 * 0.1 = 0.2 kg
        stock = StockEntrepot.objects.get(produit=self.farine, entrepot=self.entrepot)
        self.assertAlmostEqual(float(stock.quantite), 9.8)

    def test_double_paiement_refuse(self):
        CommandeSettlementService.regler(
            commande=self.commande, montant=2000,
            mode_paiement='ESPECES', utilisateur=self.user,
        )
        with self.assertRaises(CommandeSettlementError) as ctx:
            CommandeSettlementService.regler(
                commande=self.commande, montant=2000,
                mode_paiement='ESPECES', utilisateur=self.user,
            )
        self.assertIn("déjà réglée", str(ctx.exception))

    def test_commande_annulee_refusee(self):
        self.commande.annuler()
        with self.assertRaises(CommandeSettlementError) as ctx:
            CommandeSettlementService.regler(
                commande=self.commande, montant=2000,
                mode_paiement='ESPECES', utilisateur=self.user,
            )
        self.assertIn("annulée", str(ctx.exception))

    def test_montant_zero_refuse(self):
        with self.assertRaises(CommandeSettlementError):
            CommandeSettlementService.regler(
                commande=self.commande, montant=0,
                mode_paiement='ESPECES', utilisateur=self.user,
            )

    def test_stock_insuffisant_annule_paiement(self):
        # Rendre le stock insuffisant : besoin = 0.2 kg pour 2 portions
        # On laisse 0.1 kg seulement → insuffisant
        MouvementStockService.sortie_stock(
            self.farine, self.entrepot, Decimal('9.9'), "Test",
            motif=SourceOperationType.PRODUCTION, reference="PRE-TEST",
        )
        stock_restant = StockEntrepot.objects.get(produit=self.farine, entrepot=self.entrepot).quantite
        self.assertAlmostEqual(float(stock_restant), 0.1)

        with self.assertRaises(ValidationError):
            CommandeSettlementService.regler(
                commande=self.commande, montant=2000,
                mode_paiement='ESPECES', utilisateur=self.user,
            )

        self.caisse.refresh_from_db()
        self.assertEqual(self.caisse.solde, 0)
        self.commande.refresh_from_db()
        self.assertNotEqual(self.commande.statut, 'PAYEE')
        self.assertIsNone(self.commande.vente_id)

    def test_lignes_vente_avec_cout_et_marge(self):
        result = CommandeSettlementService.regler(
            commande=self.commande, montant=2000,
            mode_paiement='ESPECES', utilisateur=self.user,
        )
        vente = result['vente']
        ligne_vente = vente.lignes.first()
        # Coût = recette.cout_unitaire_rendement() = 1000/10 = 100
        # Pour 2 portions: marge = (1000 - 100) * 2 = 1800
        self.assertEqual(ligne_vente.cout_revient, Decimal('100'))
        self.assertIsNotNone(vente.cout_revient_total)
        self.assertIsNotNone(vente.marge_totale)

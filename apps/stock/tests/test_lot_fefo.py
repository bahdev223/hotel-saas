from datetime import date, timedelta
from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.stock.models import (
    Produit, Entrepot, LotProduit, StockLotEntrepot,
    StockEntrepot, UniteMesure,
)
from apps.stock.services.lot_allocation_service import LotAllocationService
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.enums.sources import SourceOperationType


class LotFEFOTest(TestCase):
    def setUp(self):
        self.unite, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.produit = Produit.objects.create(
            code="FARINE", nom="Farine", prix_achat=1000, unite_mesure=self.unite,
        )

        # Créer stock sans lot via entree_stock (sans lot_numero)
        MouvementStockService.entree_stock(
            self.produit, self.entrepot, 10, "Test",
            motif=SourceOperationType.ACHAT, valeur_unitaire=1000,
        )

    def test_verifier_coherence_ecart_detecte(self):
        ecarts = LotAllocationService.verifier_coherence()
        # StockEntrepot = 10, StockLotEntrepot = 0 (pas de lots)
        self.assertEqual(len(ecarts), 1)
        self.assertEqual(ecarts[0]['ecart'], Decimal('10'))

    def test_verifier_coherence_ok_apres_entree_lot(self):
        from apps.stock.models import MouvementStock
        mouvement = MouvementStock.objects.create(
            produit=self.produit, entrepot_dest=self.entrepot,
            type_mouvement='ENTREE', motif=SourceOperationType.ACHAT,
            quantite=10, utilisateur="Test",
        )
        LotAllocationService.entree_lot(mouvement, "LOT-001", 10, date_peremption=date(2027, 1, 1))

        ecarts = LotAllocationService.verifier_coherence()
        self.assertEqual(len(ecarts), 0)


class LotPeremptionTest(TestCase):
    def setUp(self):
        self.unite, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.produit = Produit.objects.create(
            code="LAIT", nom="Lait", prix_achat=500, unite_mesure=self.unite,
        )

        lot = LotProduit.objects.create(
            produit=self.produit, numero="LAIT-001",
            date_peremption=date.today() + timedelta(days=3),
        )
        StockLotEntrepot.objects.create(lot=lot, entrepot=self.entrepot, quantite=50)

        lot2 = LotProduit.objects.create(
            produit=self.produit, numero="LAIT-002",
            date_peremption=date.today() + timedelta(days=30),
        )
        StockLotEntrepot.objects.create(lot=lot2, entrepot=self.entrepot, quantite=100)

    def test_alertes_peremption_dans_7_jours(self):
        alertes = LotAllocationService.alertes_peremption(jours=7)
        self.assertEqual(len(alertes), 1)
        self.assertEqual(alertes[0]['lot_numero'], "LAIT-001")

    def test_alertes_peremption_dans_30_jours(self):
        alertes = LotAllocationService.alertes_peremption(jours=30)
        self.assertEqual(len(alertes), 2)

    def test_alertes_vide_si_aucun_lot_expire(self):
        alertes = LotAllocationService.alertes_peremption(jours=0)
        self.assertEqual(len(alertes), 0)

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from apps.stock.models import Produit, Entrepot, StockEntrepot, JournalStock
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.enums.sources import SourceOperationType

User = get_user_model()

class TestMouvementSorties(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.entrepot = Entrepot.objects.create(nom="Magasin Central")
        self.produit = Produit.objects.create(
            code="P002",
            nom="Test Produit 2",
            prix_achat=Decimal('100.00'),
            methode_valorisation="CUMP"
        )
        
        # Init stock
        MouvementStockService.entree_stock(
            produit=self.produit,
            entrepot=self.entrepot,
            quantite=20,
            valeur_unitaire=100,
            utilisateur=self.user,
            motif=SourceOperationType.ACHAT
        )

    def test_sortie_simple(self):
        mouvement = MouvementStockService.sortie_stock(
            produit=self.produit,
            entrepot=self.entrepot,
            quantite=5,
            utilisateur=self.user,
            motif=SourceOperationType.VENTE,
            reference="VNT-001"
        )
        
        stock = StockEntrepot.objects.get(produit=self.produit, entrepot=self.entrepot)
        self.assertEqual(stock.quantite, Decimal('15'))
        
        journal = JournalStock.objects.get(mouvement=mouvement)
        self.assertEqual(journal.stock_avant, Decimal('20'))
        self.assertEqual(journal.stock_apres, Decimal('15'))
        self.assertEqual(journal.quantite_mouvement, Decimal('-5'))

    def test_sortie_stock_insuffisant(self):
        with self.assertRaises(ValidationError):
            MouvementStockService.sortie_stock(
                produit=self.produit,
                entrepot=self.entrepot,
                quantite=50, # greater than 20
                utilisateur=self.user,
                motif=SourceOperationType.VENTE
            )

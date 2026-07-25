from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.stock.models import Produit, Entrepot, StockEntrepot, JournalStock
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.enums.sources import SourceOperationType

User = get_user_model()

class TestMouvementEntrees(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.entrepot = Entrepot.objects.create(nom="Magasin Central")
        self.produit = Produit.objects.create(
            code="P001",
            nom="Test Produit",
            prix_achat=Decimal('100.00'),
            methode_valorisation="CUMP"
        )

    def test_entree_simple(self):
        mouvement = MouvementStockService.entree_stock(
            produit=self.produit,
            entrepot=self.entrepot,
            quantite=10,
            valeur_unitaire=100,
            utilisateur=self.user,
            motif=SourceOperationType.ACHAT,
            reference="ACH-001"
        )
        
        # Vérifier le stock
        stock = StockEntrepot.objects.get(produit=self.produit, entrepot=self.entrepot)
        self.assertEqual(stock.quantite, Decimal('10'))
        
        # Vérifier la source
        self.assertIsNotNone(mouvement.source_operation)
        self.assertEqual(mouvement.source_operation.reference, "ACH-001")
        
        # Vérifier le journal
        journal = JournalStock.objects.get(mouvement=mouvement)
        self.assertEqual(journal.stock_avant, Decimal('0'))
        self.assertEqual(journal.stock_apres, Decimal('10'))
        self.assertEqual(journal.quantite_mouvement, Decimal('10'))
        self.assertEqual(journal.valeur_mouvement, Decimal('1000'))

    def test_entree_quantite_invalide(self):
        from django.core.exceptions import ValidationError
        with self.assertRaises(ValidationError):
            MouvementStockService.entree_stock(
                produit=self.produit,
                entrepot=self.entrepot,
                quantite=-5,
                valeur_unitaire=100,
                utilisateur=self.user,
                motif=SourceOperationType.ACHAT
            )

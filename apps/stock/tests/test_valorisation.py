from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.stock.models import Produit, Entrepot, StockEntrepot
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.services.valorisation_stock_service import ValorisationStockService
from apps.stock.enums.sources import SourceOperationType

User = get_user_model()

class TestValorisationStock(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        self.entrepot = Entrepot.objects.create(nom="Magasin Central")
        self.produit = Produit.objects.create(
            code="P003",
            nom="Test Produit 3",
            prix_achat=Decimal('100.00'),
            methode_valorisation="CUMP"
        )

    def test_cump_apres_plusieurs_entrees(self):
        # 1ere entrée : 10 unités à 100 FCFA
        MouvementStockService.entree_stock(
            produit=self.produit,
            entrepot=self.entrepot,
            quantite=10,
            valeur_unitaire=100,
            utilisateur=self.user,
            motif=SourceOperationType.ACHAT
        )
        
        cout_cump = ValorisationStockService.get_cout_sortie(
            produit=self.produit,
            entrepot=self.entrepot,
            quantite=5
        )
        self.assertEqual(cout_cump, Decimal('100.00'))
        
        # 2eme entrée : 10 unités à 150 FCFA
        # Le CUMP devrait devenir (10*100 + 10*150) / 20 = 125
        MouvementStockService.entree_stock(
            produit=self.produit,
            entrepot=self.entrepot,
            quantite=10,
            valeur_unitaire=150,
            utilisateur=self.user,
            motif=SourceOperationType.ACHAT
        )
        
        # NOTE: Notre implémentation actuelle de _cout_cump utilise le prix_achat de StockEntrepot mis à jour par entree_stock
        stock = StockEntrepot.objects.get(produit=self.produit, entrepot=self.entrepot)
        self.assertEqual(stock.prix_achat, Decimal('125.00'))
        
        cout_cump = ValorisationStockService.get_cout_sortie(
            produit=self.produit,
            entrepot=self.entrepot,
            quantite=5
        )
        self.assertEqual(cout_cump, Decimal('125.00'))


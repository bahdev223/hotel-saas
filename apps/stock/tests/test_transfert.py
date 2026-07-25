from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from apps.stock.models import (
    Produit, Entrepot, StockEntrepot, TransfertStock, LigneTransfertStock, SourceOperation, MouvementStock
)
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.services.transfert_service import TransfertService
from apps.stock.enums.mouvements import TypeMouvement
from apps.stock.enums.sources import SourceOperationType

User = get_user_model()

class TransfertServiceTest(TestCase):
    
    def setUp(self):
        self.user = User.objects.create_user(username="testuser", password="password")
        
        self.entrepot_source = Entrepot.objects.create(nom="Cuisine A", code="CA", type_entrepot="DEPOT")
        self.entrepot_dest = Entrepot.objects.create(nom="Cuisine B", code="CB", type_entrepot="DEPOT")
        
        self.produit = Produit.objects.create(nom="Farine", unite_base="kg", prix_achat=Decimal("1.50"))
        
        # Initialize stock
        MouvementStockService.entree_stock(
            produit=self.produit,
            entrepot=self.entrepot_source,
            quantite=Decimal("100"),
            utilisateur=self.user,
            motif=SourceOperationType.ACHAT,
            valeur_unitaire=Decimal("1.50"),
            raison="Stock initial"
        )
        
    def test_transfert_reussi(self):
        entree = TransfertService.transfert_entre_entrepots(
            produit_id=self.produit.id,
            quantite=Decimal("20"),
            entrepot_source_id=self.entrepot_source.id,
            entrepot_dest_id=self.entrepot_dest.id,
            utilisateur=self.user,
            reference="TR-001"
        )
        
        # Verify stocks
        stock_source = StockEntrepot.objects.get(produit=self.produit, entrepot=self.entrepot_source)
        stock_dest = StockEntrepot.objects.get(produit=self.produit, entrepot=self.entrepot_dest)
        
        self.assertEqual(stock_source.quantite, Decimal("80"))
        self.assertEqual(stock_dest.quantite, Decimal("20"))
        
        # Verify TransfertStock creation
        transfert = TransfertStock.objects.first()
        self.assertIsNotNone(transfert)
        self.assertEqual(transfert.entrepot_source, self.entrepot_source)
        self.assertEqual(transfert.entrepot_dest, self.entrepot_dest)
        
        # Verify LigneTransfertStock creation
        ligne = transfert.lignes.first()
        self.assertEqual(ligne.produit, self.produit)
        self.assertEqual(ligne.quantite, Decimal("20"))
        
        # Verify SourceOperation
        source_op = transfert.source_operation
        self.assertEqual(source_op.type_source, SourceOperationType.TRANSFERT)
        self.assertEqual(source_op.reference, "TR-001")
        
        # Verify MouvementStock
        sorties = MouvementStock.objects.filter(source_operation=source_op, type_mouvement=TypeMouvement.TRANSFERT_SORTIE)
        entrees = MouvementStock.objects.filter(source_operation=source_op, type_mouvement=TypeMouvement.TRANSFERT_ENTREE)
        
        self.assertEqual(sorties.count(), 1)
        self.assertEqual(entrees.count(), 1)
        
        self.assertEqual(sorties.first().entrepot_source, self.entrepot_source)
        self.assertEqual(entrees.first().entrepot_dest, self.entrepot_dest)
        
    def test_annulation_transfert(self):
        # Create transfert
        TransfertService.transfert_entre_entrepots(
            produit_id=self.produit.id,
            quantite=Decimal("20"),
            entrepot_source_id=self.entrepot_source.id,
            entrepot_dest_id=self.entrepot_dest.id,
            utilisateur=self.user,
            reference="TR-002"
        )
        
        transfert = TransfertStock.objects.last()
        self.assertIsNotNone(transfert)
        
        # Annuler
        TransfertService.annuler_transfert(transfert, self.user)
        
        # Verify stocks are back to normal
        stock_source = StockEntrepot.objects.get(produit=self.produit, entrepot=self.entrepot_source)
        stock_dest = StockEntrepot.objects.get(produit=self.produit, entrepot=self.entrepot_dest)
        
        self.assertEqual(stock_source.quantite, Decimal("100"))
        self.assertEqual(stock_dest.quantite, Decimal("0"))
        
        # Verify Transfert status
        transfert.refresh_from_db()
        self.assertEqual(transfert.statut, "ANNULE")
        
        # Verify New Source Operation for annulation
        annulations = SourceOperation.objects.filter(type_source=SourceOperationType.ANNULATION)
        self.assertEqual(annulations.count(), 1)
        
        annulation_op = annulations.first()
        
        # Verify inverse movements
        mouvements_inverses = MouvementStock.objects.filter(source_operation=annulation_op)
        self.assertEqual(mouvements_inverses.count(), 2)

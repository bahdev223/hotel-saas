from decimal import Decimal
from django.test import TestCase
from django.contrib.auth.models import User
from apps.rh.models import Employe
from apps.stock.models import Produit, Entrepot, UniteMesure, ConversionUnite, StockEntrepot
from apps.restaurant.models.recette import RecetteModel, IngredientModel
from apps.restaurant.models.production import Production, ProductionLigne, ProductionIngredient
from apps.restaurant.services.production_service import ProductionService
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.enums.sources import SourceOperationType


class ProductionResultatTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cuistot", password="test")
        self.employe = Employe.objects.create(user=self.user, nom="Chef", prenom="Test")
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.unite_piece, _ = UniteMesure.objects.get_or_create(symbole="piece", defaults={"nom": "Pièce", "type_unite": "UNITE"})
        ConversionUnite.objects.get_or_create(unite_source=self.unite_kg, unite_dest=self.unite_kg, defaults={"facteur": 1})

        self.entrepot_source = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.entrepot_dest = Entrepot.objects.create(nom="Buffet", code="BUFFET")

        self.farine = Produit.objects.create(code="FARINE", nom="Farine", prix_achat=1000, unite_mesure=self.unite_kg)
        self.gateau = Produit.objects.create(code="GATEAU", nom="Gateau", prix_achat=0, unite_mesure=self.unite_piece)

        MouvementStockService.entree_stock(
            self.farine, self.entrepot_source, 10, "Test",
            motif=SourceOperationType.ACHAT, valeur_unitaire=1000,
        )

        self.recette = RecetteModel.objects.create(
            nom="Gateau", type_recette='DESSERT',
            rendement_quantite=1, produit_fini=self.gateau,
        )
        IngredientModel.objects.create(
            recette=self.recette, produit=self.farine,
            quantite=0.5, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE',
        )

        self.production = Production.objects.create(
            numero="PRD-TEST",
            entrepot_source=self.entrepot_source,
            entrepot_dest=self.entrepot_dest,
        )
        self.ligne = ProductionLigne.objects.create(
            production=self.production, recette=self.recette, quantite=4,
        )

    def test_cout_theorique_calcule(self):
        # 4 gateaux x 0.5 kg x 1000 F = 2000
        self.assertEqual(self.production.cout_theorique, Decimal('2000'))

    def test_cout_reel_apres_validation(self):
        # Don't have an employe, use string
        ProductionService.valider_production(self.production, self.employe)

        self.production.refresh_from_db()
        self.assertEqual(self.production.statut, 'VALIDE')

        # Check actual stock was consumed
        stock = StockEntrepot.objects.get(produit=self.farine, entrepot=self.entrepot_source)
        self.assertEqual(stock.quantite, Decimal('8'))  # 10 - (4 * 0.5) = 8

        # Check ProductionIngredient was created with cout_unitaire
        pi = ProductionIngredient.objects.filter(production=self.production).first()
        self.assertIsNotNone(pi)
        self.assertEqual(pi.cout_unitaire, Decimal('1000'))

        # Check cout_reel_ligne was computed
        self.ligne.refresh_from_db()
        # 4 x 0.5 kg x 1000 F = 2000
        self.assertEqual(self.ligne.cout_reel_ligne, Decimal('2000'))

    def test_quantite_reelle(self):
        self.ligne.quantite_reelle = Decimal('3.5')
        self.ligne.save()
        self.assertEqual(self.production.total_unites_reelles, Decimal('3.5'))
        self.assertEqual(self.production.total_unites, Decimal('4'))

from decimal import Decimal
from django.test import TestCase
from apps.stock.models import Produit, Entrepot, UniteMesure, ConversionUnite, StockEntrepot
from apps.restaurant.models.recette import RecetteModel, IngredientModel
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.enums.sources import SourceOperationType

class TestRecetteConversionUnite(TestCase):
    def setUp(self):
        # 1. Création des Unités
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kilogramme", "type_unite": "MASSE"})
        self.unite_g, _ = UniteMesure.objects.get_or_create(symbole="g", defaults={"nom": "Gramme", "type_unite": "MASSE"})
        self.unite_piece, _ = UniteMesure.objects.get_or_create(symbole="piece", defaults={"nom": "Pièce", "type_unite": "UNITE"})
        ConversionUnite.objects.get_or_create(unite_source=self.unite_kg, unite_dest=self.unite_g, defaults={"facteur": 1000})

        # 2. Création de l'Entrepôt et du Produit
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.farine = Produit.objects.create(
            code="FARINE", nom="Farine", prix_achat=1000, unite_mesure=self.unite_kg
        )

        # Mettre 2 Kg de farine en stock (CUMP = 1000)
        MouvementStockService.entree_stock(
            produit=self.farine,
            entrepot=self.entrepot,
            quantite=2,
            valeur_unitaire=1000,
            utilisateur="Test",
            motif=SourceOperationType.ACHAT
        )

        # 3. Création de la Recette
        self.recette = RecetteModel.objects.create(
            nom="Gâteau au Chocolat",
            type_recette='DESSERT',
            rendement_quantite=1,
            rendement_unite_mesure=self.unite_piece
        )

        # Ingrédient : 250 g de farine
        IngredientModel.objects.create(
            recette=self.recette,
            produit=self.farine,
            quantite=250,
            unite_mesure=self.unite_g,
            type_ingredient='DEDUIRE'
        )

    def test_cout_ingredients_avec_conversion(self):
        # Le produit Farine coûte 1000 FCFA pour 1 Kg
        # L'ingrédient utilise 250 g (soit 0.25 Kg)
        # Le coût devrait être 1000 * 0.25 = 250 FCFA
        cout = self.recette.cout_revient({self.farine.code: self.farine.prix_achat})
        self.assertEqual(cout, Decimal('250.00'))

    def test_consommer_ingredients_deduit_bonne_quantite(self):
        # Initialement, on a 2 Kg en stock
        stock_initial = StockEntrepot.objects.get(produit=self.farine, entrepot=self.entrepot).quantite
        self.assertEqual(stock_initial, Decimal('2.00'))

        # On consomme la recette (1 fois)
        self.recette.consommer_ingredients(quantite=1, entrepot=self.entrepot)

        # Le stock devrait avoir diminué de 0.25 Kg (il reste 1.75 Kg)
        stock_final = StockEntrepot.objects.get(produit=self.farine, entrepot=self.entrepot).quantite
        self.assertEqual(stock_final, Decimal('1.75'))

    def test_verifier_disponibilite(self):
        dispo = self.recette.verifier_disponibilite(quantite=1, entrepot=self.entrepot)
        self.assertTrue(dispo['disponible'])
        
        # Si on veut produire 10 gâteaux, on aura besoin de 2.5 Kg.
        # Mais on a que 2 Kg en stock.
        dispo_echec = self.recette.verifier_disponibilite(quantite=10, entrepot=self.entrepot)
        self.assertFalse(dispo_echec['disponible'])
        self.assertEqual(dispo_echec['manques'][0]['besoin'], Decimal('2.50'))

from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.stock.models import Produit, Entrepot, UniteMesure, StockEntrepot
from apps.restaurant.models.recette import RecetteModel, IngredientModel
from apps.restaurant.models.menu import MenuModel, LigneMenuModel
from apps.restaurant.models.choix import ChoixLigneCommande
from apps.restaurant.services.consumption_service import RestaurantConsumptionService
from apps.stock.services.mouvement_service import MouvementStockService
from apps.stock.enums.sources import SourceOperationType
from apps.pos.models import Commande, LigneCommande, PointVente


class TestCoutParRendement(TestCase):
    def setUp(self):
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.unite_g, _ = UniteMesure.objects.get_or_create(symbole="g", defaults={"nom": "g", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")

        self.farine = Produit.objects.create(code="FARINE", nom="Farine", prix_achat=1000, unite_mesure=self.unite_kg)
        MouvementStockService.entree_stock(self.farine, self.entrepot, 10, "Test", motif=SourceOperationType.ACHAT, valeur_unitaire=1000)

        self.recette = RecetteModel.objects.create(
            nom="Gateau",
            type_recette='DESSERT',
            rendement_quantite=10,
            rendement_unite_mesure=self.unite_kg,
        )
        IngredientModel.objects.create(
            recette=self.recette, produit=self.farine,
            quantite=1, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE'
        )

    def test_cout_unitaire_rendement_divise_par_rendement(self):
        # 1 kg farine = 1000 FCFA, rendement 10 portions -> 100 F/portion
        cout = self.recette.cout_unitaire_rendement()
        self.assertEqual(cout, Decimal('100'))

    def test_cout_total_preparation_ignore_rendement(self):
        # cout_total = 1000 (le cout de 1kg d'ingredient)
        cout = self.recette.cout_total_preparation()
        self.assertEqual(cout, Decimal('1000'))

    def test_ligne_menu_utilise_cout_unitaire_rendement(self):
        menu = MenuModel.objects.create(code="M-GAT", nom="Menu Gateau", prix_vente=2000)
        ligne = LigneMenuModel.objects.create(
            id="LG-TEST", menu=menu, recette=self.recette,
            quantite=2, type_ligne='FIXE', groupe='DESSERT'
        )
        # 2 portions x 100 F = 200 F
        cout = ligne.get_cout()
        self.assertEqual(cout, Decimal('200'))


class TestMenuAvecChoix(TestCase):
    def setUp(self):
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.unite_g, _ = UniteMesure.objects.get_or_create(symbole="g", defaults={"nom": "g", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.point_vente = PointVente.objects.create(code="PV-TEST", nom="Test", type="RESTAURANT")

        self.riz = Produit.objects.create(code="RIZ", nom="Riz", prix_achat=500, unite_mesure=self.unite_kg)
        self.poulet = Produit.objects.create(code="POULET", nom="Poulet", prix_achat=2000, unite_mesure=self.unite_kg)
        self.frites = Produit.objects.create(code="FRITES", nom="Frites", prix_achat=300, unite_mesure=self.unite_kg)

        for p in [self.riz, self.poulet, self.frites]:
            MouvementStockService.entree_stock(p, self.entrepot, 10, "Test", motif=SourceOperationType.ACHAT, valeur_unitaire=p.prix_achat)

        self.riz_plat = RecetteModel.objects.create(nom="Riz sauce", type_recette='PLAT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.riz_plat, produit=self.riz, quantite=0.2, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

        self.poulet_grille = RecetteModel.objects.create(nom="Poulet grille", type_recette='PLAT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.poulet_grille, produit=self.poulet, quantite=0.2, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

        self.frites_accomp = RecetteModel.objects.create(nom="Frites", type_recette='ACCOMPAGNEMENT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.frites_accomp, produit=self.frites, quantite=0.15, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

        self.salade = RecetteModel.objects.create(nom="Salade", type_recette='ACCOMPAGNEMENT', rendement_quantite=1)

        self.menu = MenuModel.objects.create(code="M-POU", nom="Poulet Frites", prix_vente=3000)
        self.ligne_fixe = LigneMenuModel.objects.create(
            id="LF-01", menu=self.menu, recette=self.poulet_grille,
            quantite=1, type_ligne='FIXE', groupe='PLAT'
        )
        self.ligne_choix_frites = LigneMenuModel.objects.create(
            id="LC-01", menu=self.menu, recette=self.frites_accomp,
            quantite=1, type_ligne='CHOIX', groupe='ACCOMPAGNEMENT'
        )
        self.ligne_choix_salade = LigneMenuModel.objects.create(
            id="LC-02", menu=self.menu, recette=self.salade,
            quantite=1, type_ligne='CHOIX', groupe='ACCOMPAGNEMENT'
        )

    def test_menu_cout_choix_prend_max(self):
        # fixe: poulet 0.2kg*2000=400; choix max = frites 0.15*300=45 > salade 0
        # total max = 445
        cout = self.menu.get_cout_revient_total()
        self.assertEqual(cout, Decimal('445'))

    def test_commande_avec_choix_cree_choixlignecommande(self):
        commande = Commande.objects.create(
            point_vente=self.point_vente, entrepot=self.entrepot,
            type_commande='SUR_PLACE', montant_total=3000
        )
        ligne = LigneCommande.objects.create(
            commande=commande, menu=self.menu,
            quantite=1, prix_unitaire=3000
        )
        choix = ChoixLigneCommande.objects.create(
            ligne_commande=ligne,
            groupe='ACCOMPAGNEMENT',
            recette=self.frites_accomp,
            ligne_menu=self.ligne_choix_frites,
            quantite=1,
            nom_recette_snapshot=self.frites_accomp.nom,
            cout_unitaire_snapshot=self.frites_accomp.cout_unitaire_rendement(),
        )
        self.assertEqual(ligne.choix_menu.count(), 1)
        self.assertEqual(choix.recette.nom, "Frites")

    def test_consommation_choix_consomme_ingredients(self):
        commande = Commande.objects.create(
            point_vente=self.point_vente, entrepot=self.entrepot,
            type_commande='SUR_PLACE', montant_total=3000
        )
        ligne = LigneCommande.objects.create(
            commande=commande, menu=self.menu,
            quantite=1, prix_unitaire=3000
        )
        ChoixLigneCommande.objects.create(
            ligne_commande=ligne,
            groupe='ACCOMPAGNEMENT',
            recette=self.frites_accomp,
            ligne_menu=self.ligne_choix_frites,
            quantite=1,
        )
        stock_initial = StockEntrepot.objects.get(produit=self.poulet, entrepot=self.entrepot).quantite
        self.assertEqual(stock_initial, Decimal('10'))

        RestaurantConsumptionService.consommer_commande(commande, self.entrepot)

        stock_poulet = StockEntrepot.objects.get(produit=self.poulet, entrepot=self.entrepot).quantite
        stock_frites = StockEntrepot.objects.get(produit=self.frites, entrepot=self.entrepot).quantite

        # poulet 0.2kg consomme, frites 0.15kg consomme
        self.assertEqual(stock_poulet, Decimal('9.8'))
        self.assertEqual(stock_frites, Decimal('9.85'))


class TestIdempotence(TestCase):
    def setUp(self):
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.riz = Produit.objects.create(code="RIZ", nom="Riz", prix_achat=500, unite_mesure=self.unite_kg)
        MouvementStockService.entree_stock(self.riz, self.entrepot, 10, "Test", motif=SourceOperationType.ACHAT, valeur_unitaire=500)

        self.recette = RecetteModel.objects.create(nom="Riz blanc", type_recette='PLAT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.recette, produit=self.riz, quantite=1, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

        self.point_vente = PointVente.objects.create(code="PV-IDEM", nom="Test", type="RESTAURANT")
        self.commande = Commande.objects.create(
            point_vente=self.point_vente, entrepot=self.entrepot,
            type_commande='SUR_PLACE', montant_total=1000
        )
        LigneCommande.objects.create(commande=self.commande, recette=self.recette, quantite=1, prix_unitaire=1000)

    def test_commande_consommee_une_seule_fois(self):
        r1 = RestaurantConsumptionService.consommer_commande(self.commande, self.entrepot)
        self.assertTrue(r1['success'])
        self.assertFalse(r1['idempotent'])

        stock_apres = StockEntrepot.objects.get(produit=self.riz, entrepot=self.entrepot).quantite
        self.assertEqual(stock_apres, Decimal('9'))

        r2 = RestaurantConsumptionService.consommer_commande(self.commande, self.entrepot)
        self.assertTrue(r2['success'])
        self.assertTrue(r2['idempotent'])

        stock_identique = StockEntrepot.objects.get(produit=self.riz, entrepot=self.entrepot).quantite
        self.assertEqual(stock_identique, Decimal('9'))


class TestRollbackComplet(TestCase):
    def setUp(self):
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.riz = Produit.objects.create(code="RIZ", nom="Riz", prix_achat=500, unite_mesure=self.unite_kg)
        self.sel = Produit.objects.create(code="SEL", nom="Sel", prix_achat=100, unite_mesure=self.unite_kg)
        MouvementStockService.entree_stock(self.riz, self.entrepot, 1, "Test", motif=SourceOperationType.ACHAT, valeur_unitaire=500)
        MouvementStockService.entree_stock(self.sel, self.entrepot, 1, "Test", motif=SourceOperationType.ACHAT, valeur_unitaire=100)

        self.recette1 = RecetteModel.objects.create(nom="Plat avec riz", type_recette='PLAT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.recette1, produit=self.riz, quantite=1, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

        self.recette2 = RecetteModel.objects.create(nom="Plat avec sel", type_recette='PLAT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.recette2, produit=self.sel, quantite=5, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

        self.point_vente = PointVente.objects.create(code="PV-ROLL", nom="Test", type="RESTAURANT")
        self.commande = Commande.objects.create(
            point_vente=self.point_vente, entrepot=self.entrepot,
            type_commande='SUR_PLACE', montant_total=2000
        )

    def test_aucun_stock_ne_bouge_si_un_ingredient_manque(self):
        stock_riz_avant = StockEntrepot.objects.get(produit=self.riz, entrepot=self.entrepot).quantite
        stock_sel_avant = StockEntrepot.objects.get(produit=self.sel, entrepot=self.entrepot).quantite

        LigneCommande.objects.create(commande=self.commande, recette=self.recette1, quantite=1, prix_unitaire=1000)
        LigneCommande.objects.create(commande=self.commande, recette=self.recette2, quantite=1, prix_unitaire=1000)

        with self.assertRaises(ValidationError):
            RestaurantConsumptionService.consommer_commande(self.commande, self.entrepot)

        stock_riz_apres = StockEntrepot.objects.get(produit=self.riz, entrepot=self.entrepot).quantite
        stock_sel_apres = StockEntrepot.objects.get(produit=self.sel, entrepot=self.entrepot).quantite

        self.assertEqual(stock_riz_avant, stock_riz_apres)
        self.assertEqual(stock_sel_avant, stock_sel_apres)


class TestAgregationBesoins(TestCase):
    def setUp(self):
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.entrepot = Entrepot.objects.create(nom="Cuisine", code="CUISINE")
        self.farine = Produit.objects.create(code="FARINE", nom="Farine", prix_achat=1000, unite_mesure=self.unite_kg)
        MouvementStockService.entree_stock(self.farine, self.entrepot, 1.5, "Test", motif=SourceOperationType.ACHAT, valeur_unitaire=1000)

        self.recette_a = RecetteModel.objects.create(nom="Recette A", type_recette='DESSERT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.recette_a, produit=self.farine, quantite=1, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

        self.recette_b = RecetteModel.objects.create(nom="Recette B", type_recette='DESSERT', rendement_quantite=1)
        IngredientModel.objects.create(recette=self.recette_b, produit=self.farine, quantite=1, unite_mesure=self.unite_kg, type_ingredient='DEDUIRE')

    def test_besoins_communs_agreges(self):
        point_vente = PointVente.objects.create(code="PV-AGREG", nom="Test", type="RESTAURANT")
        commande = Commande.objects.create(
            point_vente=point_vente, entrepot=self.entrepot,
            type_commande='SUR_PLACE', montant_total=2000
        )
        LigneCommande.objects.create(commande=commande, recette=self.recette_a, quantite=1, prix_unitaire=1000)
        LigneCommande.objects.create(commande=commande, recette=self.recette_b, quantite=1, prix_unitaire=1000)

        result = RestaurantConsumptionService.verifier_disponibilite_commande(commande, self.entrepot)
        self.assertFalse(result['disponible'])
        self.assertEqual(len(result['manques']), 1)
        self.assertEqual(result['manques'][0]['requis'], Decimal('2'))

from decimal import Decimal
from django.test import TestCase
from apps.restaurant.models.recette import RecetteModel, IngredientModel
from apps.restaurant.models.menu import MenuModel, LigneMenuModel
from apps.restaurant.services.menu_service import MenuService
from apps.stock.models import UniteMesure


class ValiderChoixMenuTest(TestCase):
    def setUp(self):
        self.unite, _ = UniteMesure.objects.get_or_create(symbole="piece", defaults={"nom": "Pièce", "type_unite": "UNITE"})

        self.steak = RecetteModel.objects.create(nom="Steak", type_recette='PLAT')
        self.poisson = RecetteModel.objects.create(nom="Poisson", type_recette='PLAT')
        self.frites = RecetteModel.objects.create(nom="Frites", type_recette='ACCOMPAGNEMENT')
        self.salade = RecetteModel.objects.create(nom="Salade", type_recette='ACCOMPAGNEMENT')

        self.menu = MenuModel.objects.create(code="M-TEST", nom="Menu Test", prix_vente=2000)

        LigneMenuModel.objects.create(
            id="LG-PLAT1", menu=self.menu, recette=self.steak,
            groupe='PLAT', type_ligne='CHOIX',
            min_choix=1, max_choix=1,
        )
        LigneMenuModel.objects.create(
            id="LG-PLAT2", menu=self.menu, recette=self.poisson,
            groupe='PLAT', type_ligne='CHOIX',
            min_choix=1, max_choix=1,
        )
        LigneMenuModel.objects.create(
            id="LG-ACC1", menu=self.menu, recette=self.frites,
            groupe='ACCOMPAGNEMENT', type_ligne='CHOIX',
            min_choix=1, max_choix=2,
        )
        LigneMenuModel.objects.create(
            id="LG-ACC2", menu=self.menu, recette=self.salade,
            groupe='ACCOMPAGNEMENT', type_ligne='CHOIX',
            min_choix=1, max_choix=2,
        )

    def test_validation_passe_choix_valides(self):
        choix = [
            {'groupe': 'PLAT', 'recette_id': self.steak.id},
            {'groupe': 'ACCOMPAGNEMENT', 'recette_id': self.frites.id},
        ]
        result = MenuService.valider_choix_menu(self.menu, choix)
        self.assertTrue(result['valid'])

    def test_validation_echoue_si_aucun_choix(self):
        result = MenuService.valider_choix_menu(self.menu, [])
        self.assertFalse(result['valid'])
        self.assertTrue(any('PLAT' in e for e in result['errors']))

    def test_validation_echoue_si_trop_de_choix(self):
        choix = [
            {'groupe': 'PLAT', 'recette_id': self.steak.id},
            {'groupe': 'PLAT', 'recette_id': self.poisson.id},
        ]
        result = MenuService.valider_choix_menu(self.menu, choix)
        self.assertFalse(result['valid'])
        self.assertTrue(any('maximum' in e for e in result['errors']))

    def test_validation_echoue_si_recette_invalide(self):
        choix = [
            {'groupe': 'PLAT', 'recette_id': 'RECETTE_INEXISTANTE'},
        ]
        result = MenuService.valider_choix_menu(self.menu, choix)
        self.assertFalse(result['valid'])

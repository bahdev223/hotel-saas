from decimal import Decimal
from django.test import TestCase
from apps.restaurant.models.recette import RecetteModel, IngredientModel
from apps.restaurant.models.version_recette import VersionRecette
from apps.stock.models import UniteMesure


class VersionRecetteModelTest(TestCase):
    def setUp(self):
        self.unite, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kg", "type_unite": "MASSE"})
        self.recette = RecetteModel.objects.create(
            nom="Sauce tomate",
            type_recette='PLAT',
            rendement_quantite=10,
        )

    def test_creer_version_brouillon(self):
        v = VersionRecette.objects.create(
            recette=self.recette,
            numero_version=1,
            nom_snapshot=self.recette.nom,
            type_recette_snapshot=self.recette.type_recette,
        )
        self.assertEqual(v.statut, 'BROUILLON')
        self.assertEqual(str(v), "Sauce tomate v1 (Brouillon)")

    def test_numero_version_incremental(self):
        VersionRecette.objects.create(
            recette=self.recette, numero_version=1,
            nom_snapshot=self.recette.nom, type_recette_snapshot=self.recette.type_recette,
        )
        v2 = VersionRecette.objects.create(
            recette=self.recette, numero_version=2,
            nom_snapshot=self.recette.nom, type_recette_snapshot=self.recette.type_recette,
        )
        self.assertEqual(v2.numero_version, 2)

    def test_unique_together_recette_version(self):
        VersionRecette.objects.create(
            recette=self.recette, numero_version=1,
            nom_snapshot=self.recette.nom, type_recette_snapshot=self.recette.type_recette,
        )
        from django.db import IntegrityError
        with self.assertRaises(IntegrityError):
            VersionRecette.objects.create(
                recette=self.recette, numero_version=1,
                nom_snapshot=self.recette.nom, type_recette_snapshot=self.recette.type_recette,
            )

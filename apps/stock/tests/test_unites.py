from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from apps.stock.models import Produit, UniteMesure, ConversionUnite, Conditionnement
from apps.stock.services.conversion_unite_service import ConversionUniteService

class TestConversionUniteService(TestCase):
    def setUp(self):
        self.unite_kg, _ = UniteMesure.objects.get_or_create(symbole="kg", defaults={"nom": "Kilogramme", "type_unite": "MASSE"})
        self.unite_g, _ = UniteMesure.objects.get_or_create(symbole="g", defaults={"nom": "Gramme", "type_unite": "MASSE"})
        self.unite_l, _ = UniteMesure.objects.get_or_create(symbole="l", defaults={"nom": "Litre", "type_unite": "VOLUME"})
        self.unite_piece, _ = UniteMesure.objects.get_or_create(symbole="piece", defaults={"nom": "Pièce", "type_unite": "UNITE"})
        
        # 1 kg = 1000 g
        ConversionUnite.objects.get_or_create(unite_source=self.unite_kg, unite_dest=self.unite_g, defaults={"facteur": 1000})
        
        self.produit = Produit.objects.create(
            code="P004", nom="Farine", prix_achat=500, unite_mesure=self.unite_kg
        )
        
        # 1 Sac = 50 kg
        self.unite_sac = UniteMesure.objects.create(nom="Sac de Farine", symbole="sac", type_unite="UNITE")
        Conditionnement.objects.create(
            produit=self.produit, nom="Sac de Farine", unite_destination=self.unite_kg, facteur=50
        )

    def test_conversion_generique(self):
        # Kg -> g
        result = ConversionUniteService.convertir(2.5, self.unite_kg, self.unite_g)
        self.assertEqual(result, Decimal('2500'))
        
        # g -> Kg (inverse automatique)
        result = ConversionUniteService.convertir(500, self.unite_g, self.unite_kg)
        self.assertEqual(result, Decimal('0.5'))

    def test_conversion_identique(self):
        result = ConversionUniteService.convertir(10, self.unite_kg, self.unite_kg)
        self.assertEqual(result, Decimal('10'))

    def test_conversion_conditionnement(self):
        # 2 Sacs = 100 kg
        result = ConversionUniteService.convertir(2, self.unite_sac, self.unite_kg, produit=self.produit)
        self.assertEqual(result, Decimal('100'))
        
        # 25 kg = 0.5 Sac
        result = ConversionUniteService.convertir(25, self.unite_kg, self.unite_sac, produit=self.produit)
        self.assertEqual(result, Decimal('0.5'))

    def test_echec_conversion_incompatible(self):
        with self.assertRaises(ValidationError):
            ConversionUniteService.convertir(1, self.unite_kg, self.unite_l)

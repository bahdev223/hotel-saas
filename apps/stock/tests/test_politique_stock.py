from decimal import Decimal
from django.test import TestCase
from apps.entreprises.models import Etablissement
from apps.stock.models import PolitiqueStockRestaurant, Entrepot
from apps.stock.services.politique_stock_service import PolitiqueStockService


class PolitiqueStockServiceTest(TestCase):
    def setUp(self):
        self.entrepot_defaut = Entrepot.objects.create(nom="Défaut", code="DEF")
        self.entrepot_etab = Entrepot.objects.create(nom="Établissement", code="ETAB")
        self.entrepot_pv = Entrepot.objects.create(nom="Point de vente", code="PV")

    def test_politique_defaut_quand_aucune_specifique(self):
        p = PolitiqueStockRestaurant.objects.create(
            entrepot_source=self.entrepot_defaut,
            mode_consommation='AUTO',
            evenement_declencheur='PAIEMENT',
        )
        result = PolitiqueStockService.get_politique()
        self.assertIsNotNone(result)
        self.assertEqual(result.entrepot_source, self.entrepot_defaut)

    def test_politique_defaut_quand_pv_sans_politique(self):
        PolitiqueStockRestaurant.objects.create(
            entrepot_source=self.entrepot_defaut,
            mode_consommation='AUTO',
            evenement_declencheur='PAIEMENT',
        )
        result = PolitiqueStockService.get_politique(point_vente=None)
        self.assertEqual(result.entrepot_source, self.entrepot_defaut)

    def test_doit_consommer_defaut_vrai(self):
        self.assertTrue(PolitiqueStockService.doit_consommer())

    def test_doit_consommer_faux_si_evenement_non_paiement(self):
        PolitiqueStockRestaurant.objects.create(
            entrepot_source=self.entrepot_defaut,
            mode_consommation='MANUEL',
            evenement_declencheur='MANUEL',
        )
        self.assertFalse(PolitiqueStockService.doit_consommer())

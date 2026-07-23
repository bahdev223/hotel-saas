from decimal import Decimal
from django.test import TestCase
from apps.comptabilite.models import CompteModel
from apps.comptabilite.services.ecriture_comptable import EcritureComptableService


class GetCompteTests(TestCase):
    """Test _get_compte resolution logic: code first, id fallback"""

    @classmethod
    def setUpTestData(cls):
        cls.compte_571 = CompteModel.objects.create(
            code='571', libelle='Caisse', type_compte='TRESORERIE', actif=True
        )
        cls.compte_419 = CompteModel.objects.create(
            code='419', libelle='Avances clients', type_compte='TIERS', actif=True
        )
        cls.compte_411 = CompteModel.objects.create(
            code='411', libelle='Clients', type_compte='TIERS', actif=True
        )
        cls.compte_401 = CompteModel.objects.create(
            code='401', libelle='Fournisseurs', type_compte='TIERS', actif=True
        )
        cls.compte_706 = CompteModel.objects.create(
            code='706', libelle='Prestations de services', type_compte='PRODUIT', actif=True
        )

    def test_get_compte_by_code_string(self):
        compte = EcritureComptableService._get_compte('571')
        self.assertIsNotNone(compte)
        self.assertEqual(compte.code, '571')

    def test_get_compte_by_code_419(self):
        compte = EcritureComptableService._get_compte('419')
        self.assertIsNotNone(compte)
        self.assertEqual(compte.code, '419')

    def test_get_compte_by_code_411(self):
        compte = EcritureComptableService._get_compte('411')
        self.assertIsNotNone(compte)
        self.assertEqual(compte.code, '411')

    def test_get_compte_by_code_401(self):
        compte = EcritureComptableService._get_compte('401')
        self.assertIsNotNone(compte)
        self.assertEqual(compte.code, '401')

    def test_get_compte_by_code_706(self):
        compte = EcritureComptableService._get_compte('706')
        self.assertIsNotNone(compte)
        self.assertEqual(compte.code, '706')

    def test_get_compte_by_id_int(self):
        compte = EcritureComptableService._get_compte(self.compte_571.id)
        self.assertIsNotNone(compte)
        self.assertEqual(compte.id, self.compte_571.id)

    def test_get_compte_by_id_string_numeric(self):
        """Numeric string that is NOT a code should fallback to id lookup"""
        compte = EcritureComptableService._get_compte(str(self.compte_571.id))
        self.assertIsNotNone(compte)
        self.assertEqual(compte.id, self.compte_571.id)

    def test_get_compte_unknown_code(self):
        compte = EcritureComptableService._get_compte('999')
        self.assertIsNone(compte)

    def test_get_compte_none(self):
        compte = EcritureComptableService._get_compte(None)
        self.assertIsNone(compte)

    def test_code_precedence_over_id(self):
        """When a string matches both a code and an id, code wins"""
        new_compte = CompteModel.objects.create(
            code='99999', libelle='Test code precedence', type_compte='CHARGE', actif=True
        )
        compte = EcritureComptableService._get_compte('99999')
        self.assertIsNotNone(compte)
        self.assertEqual(compte.code, '99999')

from decimal import Decimal
from datetime import date, timedelta
from io import StringIO

from django.test import TestCase
from django.core.management import call_command
from django.contrib.auth import get_user_model

from apps.stock.models import Produit, Entrepot, StockEntrepot, Lot, MouvementStock
from apps.stock.enums.mouvements import TypeMouvement

User = get_user_model()


class TestVerifierStock(TestCase):
    def setUp(self):
        self.entrepot = Entrepot.objects.create(nom="Magasin Central")
        self.produit = Produit.objects.create(
            code="P001", nom="Farine", prix_achat=Decimal("100.00"), methode_valorisation="CUMP"
        )

    def _run(self):
        out = StringIO()
        call_command("verifier_stock", stdout=out)
        return out.getvalue()

    def test_stock_coherent(self):
        StockEntrepot.objects.update_or_create(entrepot=self.entrepot, produit=self.produit, defaults={"quantite": Decimal("10")})
        sortie = self._run()
        self.assertIn("Aucun probleme detecte", sortie)

    def test_stock_negatif_detecte(self):
        StockEntrepot.objects.update_or_create(entrepot=self.entrepot, produit=self.produit, defaults={"quantite": Decimal("-3")})
        sortie = self._run()
        self.assertIn("négatif", sortie)
        self.assertIn("Farine", sortie)

    def test_mouvement_sans_journal_ni_source_detecte(self):
        # Mouvement créé en direct (hors service) : ni journal, ni source
        MouvementStock.objects.create(
            produit=self.produit,
            type_mouvement=TypeMouvement.SORTIE,
            quantite=Decimal("2"),
            utilisateur="test",
        )
        sortie = self._run()
        self.assertIn("journal absent", sortie)
        self.assertIn("source d'opération absente", sortie)

    def test_lot_perime_est_un_avertissement(self):
        Lot.objects.create(
            produit=self.produit,
            numero="L-EXP",
            quantite=Decimal("5"),
            quantite_restante=Decimal("5"),
            date_peremption=date.today() - timedelta(days=1),
        )
        # Aligner le stock sur le lot pour ne pas déclencher l'écart stock/lots
        StockEntrepot.objects.update_or_create(entrepot=self.entrepot, produit=self.produit, defaults={"quantite": Decimal("5")})
        sortie = self._run()
        self.assertIn("avertissement", sortie)
        self.assertIn("périmé", sortie)
        # Un lot périmé n'est pas une anomalie d'intégrité
        self.assertNotIn("anomalie(s) detectee", sortie)

    def test_ecart_stock_lots_detecte(self):
        StockEntrepot.objects.update_or_create(entrepot=self.entrepot, produit=self.produit, defaults={"quantite": Decimal("10")})
        Lot.objects.create(
            produit=self.produit, numero="L1",
            quantite=Decimal("4"), quantite_restante=Decimal("4"),
        )
        sortie = self._run()
        self.assertIn("Écart stock/lots", sortie)

    def test_strict_leve_systemexit_si_anomalie(self):
        StockEntrepot.objects.update_or_create(entrepot=self.entrepot, produit=self.produit, defaults={"quantite": Decimal("-1")})
        with self.assertRaises(SystemExit):
            call_command("verifier_stock", "--strict", stdout=StringIO())

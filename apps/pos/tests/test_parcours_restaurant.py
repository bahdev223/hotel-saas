from django.test import TestCase
from django.utils import timezone
from apps.pos.models import PointVente, SessionCaisse, Vente, LigneVente
from apps.tresorerie.models import Caisse
from apps.core.models import JourneeExploitation
from apps.stock.models import Produit, CategorieProduit
from apps.rh.models import Employe
from django.contrib.auth.models import User
from decimal import Decimal

class ParcoursRestaurantTest(TestCase):
    def setUp(self):
        # 1. Setup minimal
        self.user = User.objects.create_user(username='test', password='123')
        self.employe = Employe.objects.create(user=self.user, nom='Test', prenom='User')
        self.caisse = Caisse.objects.create(nom="Caisse", code="C1")
        self.pv = PointVente.objects.create(nom="Restau", type="RESTAURATION")
        
        # 2. Création de la Journée d'Exploitation
        self.journee = JourneeExploitation.objects.create(date_metier=timezone.now().date())
        
        # 3. Création du Produit
        self.cat = CategorieProduit.objects.create(nom="Boisson")
        self.produit = Produit.objects.create(nom="Coca", categorie=self.cat, prix_achat=300, prix_vente=1000)
        
        self.session = SessionCaisse.objects.create(point_vente=self.pv, caisse=self.caisse, ouverte_par=self.employe)

    def test_creation_vente_et_marge(self):
        # Simuler une vente encaissée directement
        vente = Vente.objects.create(
            point_vente=self.pv, caisse=self.caisse, session_caisse=self.session,
            numero="V-TEST-1", montant_total=1000, sous_total=1000,
            cout_revient_total=300, marge_totale=700, statut='PAYEE'
        )
        LigneVente.objects.create(
            vente=vente, produit=self.produit, quantite=1, prix_unitaire=1000,
            prix_catalogue=1000, cout_revient=300, marge=700
        )
        
        # Vérifications
        self.assertEqual(vente.marge_totale, Decimal('700'))
        self.assertEqual(vente.lignes.count(), 1)
        self.assertEqual(vente.statut, 'PAYEE')

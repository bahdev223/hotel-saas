from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
import random
from decimal import Decimal

class Command(BaseCommand):
    help = 'Génère des données de démonstration pour prospecter (Hôtel + Restaurant + POS)'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Début de la génération de la démo..."))
        
        # 1. Créer une Journée d'exploitation
        from apps.core.models import JourneeExploitation
        aujourdhui = timezone.now().date()
        journee, created = JourneeExploitation.objects.get_or_create(
            date_metier=aujourdhui,
            defaults={'statut': 'OUVERTE'}
        )
        if created:
            self.stdout.write(f"- Journée d'exploitation {aujourdhui} créée.")

        # 2. Créer un Utilisateur/Employé de test
        from django.contrib.auth.models import User, Group
        from apps.rh.models import Employe
        user, _ = User.objects.get_or_create(username='demo_admin', email='demo@hotel.com')
        user.set_password('demo123')
        user.save()
        employe, _ = Employe.objects.get_or_create(
            user=user,
            defaults={'nom': 'Demo', 'prenom': 'Admin', 'matricule': 'EMP001'}
        )

        # 3. Créer des Points de Vente et Caisse
        from apps.pos.models import PointVente
        from apps.tresorerie.models import Caisse
        caisse, _ = Caisse.objects.get_or_create(nom="Caisse Centrale", code="CC01")
        pv_restau, _ = PointVente.objects.get_or_create(nom="Restaurant Principal", type="RESTAURATION")
        pv_bar, _ = PointVente.objects.get_or_create(nom="Bar Piscine", type="BAR")

        # 4. Créer quelques catégories et produits
        from apps.stock.models import Categorie, Produit
        cat_boisson, _ = Categorie.objects.get_or_create(nom="Boissons Fraîches")
        p_coca, _ = Produit.objects.get_or_create(
            nom="Coca-Cola 33cl", categorie=cat_boisson, 
            defaults={'prix_achat': 300, 'prix_vente': 1000, 'type_produit': 'CONSOMMABLE'}
        )
        p_eau, _ = Produit.objects.get_or_create(
            nom="Eau Minérale 1.5L", categorie=cat_boisson, 
            defaults={'prix_achat': 200, 'prix_vente': 1000, 'type_produit': 'CONSOMMABLE'}
        )

        # 5. Créer une Session de Caisse
        from apps.pos.models import SessionCaisse
        session, _ = SessionCaisse.objects.get_or_create(
            point_vente=pv_restau,
            caisse=caisse,
            statut='OUVERTE',
            defaults={'ouverte_par': employe, 'solde_initial': 50000}
        )

        # 6. Générer quelques ventes pour gonfler les stats
        from apps.pos.models import Vente, LigneVente
        if Vente.objects.filter(session_caisse=session).count() < 10:
            for i in range(10):
                montant = Decimal(random.choice([1000, 2000, 5000, 10000]))
                cout = montant * Decimal('0.3') # 30% food cost
                marge = montant - cout
                v = Vente.objects.create(
                    point_vente=pv_restau, caisse=caisse, session_caisse=session,
                    numero=f"VDEMO-{i}-{timezone.now().timestamp()}",
                    montant_total=montant, sous_total=montant,
                    cout_revient_total=cout, marge_totale=marge,
                    statut='PAYEE', caissier=employe, encaisse_par=employe
                )
                LigneVente.objects.create(
                    vente=v, produit=p_coca, quantite=1, prix_unitaire=montant,
                    prix_catalogue=montant, cout_revient=cout, marge=marge
                )
            self.stdout.write("- 10 Ventes de démonstration générées.")

        self.stdout.write(self.style.SUCCESS("✅ Démo prête ! Tu peux te connecter avec demo_admin / demo123"))

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.entreprises.services import obtenir_etablissement_actuel
from apps.entreprises.models import Etablissement
from apps.hotel.models import TypeChambre, TypeTarif, PlanTarifaire, TarifChambre, CreneauTarifaire


class Command(BaseCommand):
    help = "Crée les données de démonstration pour la tarification"

    def handle(self, *args, **options):
        etablissement = obtenir_etablissement_actuel()
        if not etablissement:
            etablissement = Etablissement.objects.first()
        if not etablissement:
            self.stdout.write(self.style.ERROR("Aucun établissement trouvé."))
            return

        # -- Types de chambres --
        types_chambres_data = [
            ("chambre-standard", "Chambre Standard", "CHAMBRE", 2, 25, "#4A90D9", "bed"),
            ("chambre-vip", "Chambre VIP", "VIP", 2, 35, "#D4AF37", "star"),
            ("suite", "Suite", "SUITE", 4, 50, "#9B59B6", "gem"),
            ("salle-reunion", "Salle de réunion", "SALLE", 20, 40, "#2ECC71", "users"),
            ("espace", "Espace événementiel", "ESPACE", 50, 100, "#E67E22", "expand"),
        ]
        for code, nom, cat, cap, surf, color, icon in types_chambres_data:
            TypeChambre.objects.get_or_create(
                code=code,
                defaults=dict(
                    nom=nom, categorie=cat,
                    capacite_par_defaut=cap, surface_par_defaut_m2=surf,
                    couleur=color, icone=icon,
                    etablissement=etablissement,
                ),
            )
        self.stdout.write(self.style.SUCCESS(f"Types de chambres : {TypeChambre.objects.count()}"))

        # -- Types de tarif --
        types_tarif_data = [
            ("nuitee", "Nuitée", "NUITEE", 1440, 1),
            ("journee", "Journée complète", "JOURNEE", 480, 2),
            ("demi-journee", "Demi-journée", "DEMI_JOURNEE", 240, 3),
            ("heure", "Tarif horaire", "HEURE", 60, 4),
            ("semaine", "Tarif semaine", "SEMAINE", 10080, 5),
            ("mois", "Tarif mensuel", "MOIS", 43200, 6),
            ("forfait", "Forfait", "FORFAIT", None, 7),
        ]
        for code, nom, unite, duree, ordre in types_tarif_data:
            TypeTarif.objects.get_or_create(
                code=code,
                defaults=dict(nom=nom, unite_facturation=unite, duree_minutes=duree, ordre=ordre),
            )
        self.stdout.write(self.style.SUCCESS(f"Types de tarif : {TypeTarif.objects.count()}"))

        # -- Plans tarifaires --
        plans_data = [
            ("standard", "Tarif standard", "TOUS", 100, False, True),
            ("entreprise", "Tarif entreprise", "ENTREPRISE", 50, False, True),
            ("agence", "Tarif agence", "AGENCE", 60, False, True),
            ("weekend", "Tarif week-end", "TOUS", 200, False, True),
            ("haute-saison", "Haute saison", "TOUS", 250, False, True),
            ("basse-saison", "Basse saison", "TOUS", 300, False, True),
            ("petit-dejeuner", "Avec petit-déjeuner", "TOUS", 150, True, True),
        ]
        for code, nom, tc, priorite, pdej, taxes in plans_data:
            PlanTarifaire.objects.get_or_create(
                etablissement=etablissement,
                code=code,
                defaults=dict(
                    nom=nom, type_client=tc,
                    priorite=priorite,
                    petit_dejeuner_inclus=pdej,
                    taxes_incluses=taxes,
                ),
            )
        self.stdout.write(self.style.SUCCESS(f"Plans tarifaires : {PlanTarifaire.objects.count()}"))

        # -- Tarifs chambres --
        standard = TypeChambre.objects.filter(code="chambre-standard").first()
        nuit = TypeTarif.objects.filter(code="nuitee").first()
        jour = TypeTarif.objects.filter(code="journee").first()
        demi = TypeTarif.objects.filter(code="demi-journee").first()
        heure = TypeTarif.objects.filter(code="heure").first()
        plan_std = PlanTarifaire.objects.filter(etablissement=etablissement, code="standard").first()
        plan_ent = PlanTarifaire.objects.filter(etablissement=etablissement, code="entreprise").first()
        plan_we = PlanTarifaire.objects.filter(etablissement=etablissement, code="weekend").first()

        tarifs_initiaux = []
        if standard and plan_std and nuit:
            tarifs_initiaux.append((standard, plan_std, nuit, "25000"))
        if standard and plan_std and jour:
            tarifs_initiaux.append((standard, plan_std, jour, "30000"))
        if standard and plan_std and demi:
            tarifs_initiaux.append((standard, plan_std, demi, "15000"))
        if standard and plan_std and heure:
            tarifs_initiaux.append((standard, plan_std, heure, "5000"))
        if standard and plan_ent and nuit:
            tarifs_initiaux.append((standard, plan_ent, nuit, "22000"))
        if standard and plan_we and nuit:
            tarifs_initiaux.append((standard, plan_we, nuit, "28000"))

        for tc, plan, tt, montant in tarifs_initiaux:
            TarifChambre.objects.get_or_create(
                etablissement=etablissement,
                type_chambre=tc,
                plan_tarifaire=plan,
                type_tarif=tt,
                defaults=dict(montant=montant),
            )
        self.stdout.write(self.style.SUCCESS(f"Tarifs chambres : {TarifChambre.objects.count()}"))

        # -- Créneaux --
        creneaux_data = [
            (demi, "Matin", "08:00", "13:00"),
            (demi, "Après-midi", "14:00", "19:00"),
        ]
        for tt, nom, h_deb, h_fin in creneaux_data:
            if tt:
                CreneauTarifaire.objects.get_or_create(
                    type_tarif=tt,
                    nom=nom,
                    defaults=dict(heure_debut=h_deb, heure_fin=h_fin),
                )
        self.stdout.write(self.style.SUCCESS(f"Créneaux : {CreneauTarifaire.objects.count()}"))

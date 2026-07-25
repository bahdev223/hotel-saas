from decimal import Decimal

from django.core.management.base import BaseCommand

from apps.entreprises.services import obtenir_etablissement_actuel
from apps.entreprises.models import Etablissement
from apps.hotel.models import TypeChambre, UniteModel, Tarif


class Command(BaseCommand):
    help = "Crée des chambres et tarifs de démonstration (modèle simplifié : Tarif lié directement à la chambre)"

    def handle(self, *args, **options):
        etablissement = obtenir_etablissement_actuel()
        if not etablissement:
            etablissement = Etablissement.objects.first()
        if not etablissement:
            self.stdout.write(self.style.ERROR("Aucun établissement trouvé."))
            return

        # -- Types de chambres (catégorisation légère, sans lien avec le prix) --
        types_chambres_data = [
            ("chambre-standard", "Chambre Standard", "CHAMBRE", 2, 25, "#4A90D9", "bed"),
            ("chambre-vip", "Chambre VIP", "VIP", 2, 35, "#D4AF37", "star"),
            ("suite", "Suite", "SUITE", 4, 50, "#9B59B6", "gem"),
        ]
        types_crees = {}
        for code, nom, cat, cap, surf, color, icon in types_chambres_data:
            tc, _ = TypeChambre.objects.get_or_create(
                code=code,
                defaults=dict(
                    nom=nom, categorie=cat,
                    capacite_par_defaut=cap, surface_par_defaut_m2=surf,
                    couleur=color, icone=icon,
                    etablissement=etablissement,
                ),
            )
            types_crees[code] = tc
        self.stdout.write(self.style.SUCCESS(f"Types de chambres : {TypeChambre.objects.count()}"))

        # -- Chambres de démonstration --
        chambres_data = [
            ("CH-101", "Chambre 101", "chambre-standard"),
            ("CH-102", "Chambre 102", "chambre-standard"),
            ("VIP-201", "Suite VIP 201", "chambre-vip"),
        ]
        chambres_creees = {}
        for code, nom, type_code in chambres_data:
            chambre, _ = UniteModel.objects.get_or_create(
                code=code,
                defaults=dict(
                    nom=nom,
                    type_unite="CHAMBRE" if type_code != "chambre-vip" else "VIP",
                    type_chambre=types_crees[type_code],
                    capacite=types_crees[type_code].capacite_par_defaut,
                    prix=5000,       # legacy (tarif horaire de secours pour l'ancien flux POS)
                    prix_jour=25000,
                ),
            )
            chambres_creees[code] = chambre
        self.stdout.write(self.style.SUCCESS(f"Chambres : {len(chambres_creees)}"))

        # -- Tarifs multiples par chambre, directement liés (aucune configuration requise) --
        tarifs_par_chambre = {
            "CH-101": [("Nuitée", 25000), ("Demi-journée", 15000), ("Nuitée week-end", 30000)],
            "CH-102": [("Nuitée", 25000), ("Demi-journée", 15000)],
            "VIP-201": [("Nuitée", 45000), ("Nuitée week-end", 55000), ("Forfait mensuel", 900000)],
        }
        total_tarifs = 0
        for code, tarifs in tarifs_par_chambre.items():
            chambre = chambres_creees[code]
            for nom, montant in tarifs:
                _, created = Tarif.objects.get_or_create(
                    unite=chambre,
                    nom=nom,
                    defaults={"montant": Decimal(str(montant))},
                )
                if created:
                    total_tarifs += 1
        self.stdout.write(self.style.SUCCESS(f"Tarifs créés : {total_tarifs} (total en base : {Tarif.objects.count()})"))

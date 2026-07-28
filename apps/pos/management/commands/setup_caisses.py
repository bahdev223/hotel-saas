from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Cree le point de vente principal + caisses (banque, Orange Money, Moov Money)"

    def handle(self, *args, **options):
        from apps.pos.models import PointVente, CaissePointVente
        from apps.tresorerie.models import Caisse

        with transaction.atomic():
            pv, created_pv = PointVente.objects.get_or_create(
                code="RESTAURANT",
                defaults={
                    "nom": "Restaurant Principal",
                    "type": "RESTAURATION",
                    "actif": True,
                },
            )
            self._log("Point de vente", pv.nom, created_pv)

            banque, created_banque = Caisse.objects.get_or_create(
                code="BANQUE-001",
                defaults={
                    "nom": "Compte Bancaire Principal",
                    "type_financier": "BANQUE",
                    "role": "CENTRALE",
                    "solde": 0,
                    "actif": True,
                },
            )
            self._log("Caisse Banque", banque.nom, created_banque)

            om, created_om = Caisse.objects.get_or_create(
                code="OM-001",
                defaults={
                    "nom": "Orange Money",
                    "type_financier": "MOBILE_MONEY",
                    "role": "GUICHET",
                    "solde": 0,
                    "actif": True,
                },
            )
            self._log("Caisse Orange Money", om.nom, created_om)

            mm, created_mm = Caisse.objects.get_or_create(
                code="MOOV-001",
                defaults={
                    "nom": "Moov Money",
                    "type_financier": "MOBILE_MONEY",
                    "role": "GUICHET",
                    "solde": 0,
                    "actif": True,
                },
            )
            self._log("Caisse Moov Money", mm.nom, created_mm)

            for caisse in [banque, om, mm]:
                _, created_link = CaissePointVente.objects.get_or_create(
                    point_vente=pv,
                    caisse=caisse,
                    defaults={"principale": caisse == banque, "actif": True},
                )
                if created_link:
                    self.stdout.write(f"  [+] Liee {caisse.nom} -> {pv.nom}")

        # En dehors de la transaction (les unicode plantent sur Windows)
        self.stdout.write(self.style.SUCCESS("\n[OK] Configuration financiere terminee"))
        self.stdout.write(f"   Point de vente : {pv.nom} ({pv.code})")
        self.stdout.write(f"   Banque         : {banque.nom} ({banque.code})")
        self.stdout.write(f"   Orange Money   : {om.nom} ({om.code})")
        self.stdout.write(f"   Moov Money     : {mm.nom} ({mm.code})")

    def _log(self, label, nom, created):
        if created:
            self.stdout.write(f"  [+] {label} cree : {nom}")
        else:
            self.stdout.write(f"  [/] {label} deja existant : {nom}")

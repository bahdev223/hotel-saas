from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType

from apps.comptabilite.models import CompteModel
from apps.tresorerie.models import Caisse
from apps.pos.models import PointVente, PointVenteEntrepot, CaissePointVente
from apps.stock.models import Entrepot


class Command(BaseCommand):
    help = "Crée le point de vente Guichet RAF et ses dépendances"

    def handle(self, *args, **options):
        parent_571 = CompteModel.objects.filter(code='571').first()
        if not parent_571:
            self.stderr.write("Compte 571 introuvable. Charge d'abord les données avec loaddata.")
            return

        compte_571001, _ = CompteModel.objects.get_or_create(
            code='571001',
            defaults={
                'libelle': 'CAISSE CENTRALE RAF',
                'nature': 'ACTIF',
                'sens': 'DEBIT',
                'parent': parent_571,
                'niveau': 3,
                'type_compte': 'compte',
                'est_mouvement': True,
                'categorie': 'bilan',
                'actif': True,
            }
        )

        caisse_raf, _ = Caisse.objects.get_or_create(
            code='RAF-001',
            defaults={
                'nom': 'Caisse Centrale RAF',
                'type_financier': 'ESPECES',
                'role': 'CENTRALE',
                'solde': 0,
                'actif': True,
                'compte_comptable': compte_571001,
            }
        )

        point_vente, _ = PointVente.objects.get_or_create(
            code='RAF',
            defaults={
                'nom': 'Guichet RAF',
                'type': 'AUTRE',
                'actif': True,
            }
        )
        CaissePointVente.objects.get_or_create(
            point_vente=point_vente, caisse=caisse_raf,
            defaults={'principale': True, 'actif': True},
        )

        for type_ep in ['BRASSERIE', 'RESTAURANT']:
            entrepot = Entrepot.objects.filter(type_entrepot=type_ep, actif=True).first()
            if entrepot:
                PointVenteEntrepot.objects.get_or_create(
                    point_vente=point_vente, entrepot=entrepot
                )

        Group.objects.get_or_create(name='RAF')

        raf_group = Group.objects.get(name='RAF')
        pos_ct = ContentType.objects.get_for_model(PointVente)
        for codename in ['view_pointvente', 'change_pointvente']:
            try:
                perm = Permission.objects.get(codename=codename, content_type=pos_ct)
                raf_group.permissions.add(perm)
            except Permission.DoesNotExist:
                pass

        self.stdout.write(self.style.SUCCESS("Guichet RAF créé avec succès."))

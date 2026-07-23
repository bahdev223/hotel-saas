from django.core.management.base import BaseCommand
from apps.stock.models.produit import Produit
from apps.stock.models.entrepot import Entrepot
from apps.stock.models.stock_entrepot import StockEntrepot


class Command(BaseCommand):
    help = 'Crée les StockEntrepot manquants pour que tout produit soit dans tout entrepôt'

    def handle(self, *args, **options):
        produits = Produit.objects.filter(actif=True)
        entrepots = Entrepot.objects.filter(actif=True)
        total_crees = 0

        for produit in produits:
            for entrepot in entrepots:
                _, created = StockEntrepot.objects.get_or_create(
                    entrepot=entrepot,
                    produit=produit,
                    defaults={'quantite': 0}
                )
                if created:
                    total_crees += 1

        self.stdout.write(self.style.SUCCESS(
            f'{total_crees} StockEntrepot créés sur {produits.count()} produits × {entrepots.count()} entrepôts'
        ))

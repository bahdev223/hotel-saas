from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.stock.models.stock_entrepot import StockEntrepot
from apps.stock.models.mouvement import MouvementStock
from apps.stock.models.inventaire import LigneInventaire


class Command(BaseCommand):
    help = 'Corrige StockEntrepot.prix_achat=0 depuis la dernière source fiable (mouvement > inventaire > produit)'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true', help='Affiche sans modifier')
        parser.add_argument('--force', action='store_true', help='Skip confirmation')

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        force = options['force']

        stocks_zero = StockEntrepot.objects.filter(
            Q(prix_achat=0) | Q(prix_achat__isnull=True),
        ).select_related('produit', 'entrepot')

        total = stocks_zero.count()
        if total == 0:
            self.stdout.write(self.style.SUCCESS('Aucun StockEntrepot avec prix_achat=0 à corriger.'))
            return

        rows = []
        for s in stocks_zero:
            produit = s.produit
            entrepot = s.entrepot

            # Source 1 : dernier mouvement d'entrée avec valeur > 0
            mvt = MouvementStock.objects.filter(
                Q(entrepot_dest=entrepot) | Q(entrepot_source=entrepot),
                produit=produit, valeur_unitaire__gt=0
            ).order_by('-date_mouvement').first()
            prix_mvt = mvt.valeur_unitaire if mvt else None

            # Source 2 : dernier inventaire VALIDE (même logique que api_valider_inventaire)
            ligne = LigneInventaire.objects.filter(
                inventaire__entrepot=entrepot,
                inventaire__statut='VALIDE',
                produit=produit,
            ).select_related('inventaire', 'produit').order_by('-inventaire__date_fin').first()
            prix_inv = None
            if ligne:
                p = ligne.prix_unitaire or ligne.produit.prix_achat or None
                if p and p > 0:
                    prix_inv = p

            # Source 3 : Produit.prix_achat
            prix_prod = produit.prix_achat if produit.prix_achat and produit.prix_achat > 0 else None

            # Meilleure source : mvt > inventaire > produit
            meilleur_prix = prix_mvt or prix_inv or prix_prod

            if meilleur_prix is None:
                continue

            source = 'MOUVEMENT' if meilleur_prix == prix_mvt else ('INVENTAIRE' if meilleur_prix == prix_inv else 'PRODUIT')

            rows.append({
                'stock': s,
                'produit_nom': produit.nom,
                'entrepot_nom': entrepot.nom,
                'prix_mvt': prix_mvt,
                'prix_inv': prix_inv,
                'prix_prod': prix_prod,
                'retenu': meilleur_prix,
                'source': source,
            })

        if not rows:
            self.stdout.write(self.style.WARNING('Aucune source de prix trouvée pour les stocks concernés.'))
            return

        self.stdout.write(f"\n{'Produit':<35} {'Entrepôt':<20} {'Mouvt':<10} {'Invent.':<10} {'Produit':<10} {'Retenu':<10} {'Source':<15}")
        self.stdout.write('-' * 110)
        for r in rows:
            self.stdout.write(
                f"{r['produit_nom'][:34]:<35} {r['entrepot_nom'][:19]:<20} "
                f"{str(r['prix_mvt'] or '-'):<10} {str(r['prix_inv'] or '-'):<10} "
                f"{str(r['prix_prod'] or '-'):<10} {r['retenu']:<10} {r['source']:<15}"
            )

        self.stdout.write(f"\nTotal : {len(rows)} ligne(s) à corriger")

        if dry_run:
            self.stdout.write(self.style.WARNING('Dry-run — aucune modification effectuée'))
            return

        if not force:
            confirm = input(f'Corriger {len(rows)} entrées ? [y/N] ')
            if confirm.lower() != 'y':
                self.stdout.write(self.style.WARNING('Annulé'))
                return

        updated = 0
        for r in rows:
            r['stock'].prix_achat = r['retenu']
            r['stock'].save(update_fields=['prix_achat'])
            updated += 1

        self.stdout.write(self.style.SUCCESS(f'{updated}/{len(rows)} StockEntrepot corrigés'))

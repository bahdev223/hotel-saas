"""
Management commande : Nettoie les données de test et réinitialise les stocks.

Usage:
    python manage.py reset_test_data                        # Affiche le résumé sans agir
    python manage.py reset_test_data --apply                # Supprime tout
    python manage.py reset_test_data --apply --dry-run      # Simule sans écrire
    python manage.py reset_test_data --apply --force        # Skip confirmation
"""
from django.core.management.base import BaseCommand
from django.db import transaction, connection
from django.utils import timezone
from collections import defaultdict


class Command(BaseCommand):
    help = "Nettoie les données de test (ventes, commandes, sessions) et réinitialise les stocks"

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', help='Appliquer le nettoyage')
        parser.add_argument('--dry-run', action='store_true', help='Simuler sans écrire')
        parser.add_argument('--force', action='store_true', help='Skip confirmation')

    def handle(self, *args, **options):
        self.apply = options['apply']
        self.dry_run = options['dry_run']
        self.force = options['force']

        if self.dry_run and not self.apply:
            self.stderr.write("--dry-run sans --apply n'a pas de sens")
            return

        from apps.pos.models import Vente, Commande, LigneCommande, SessionCaisse
        from apps.stock.models import MouvementStock, StockEntrepot, Inventaire, LigneInventaire
        from apps.tresorerie.models import MouvementCaisse, TransfertCaisse, Caisse
        from apps.paiements.models import Paiement
        from apps.comptabilite.models.ecriture import EcritureModel, LigneEcritureModel

        today = timezone.now().date()

        # Collecter les stats
        stats = {}
        stats['ventes'] = Vente.objects.count()
        stats['commandes'] = Commande.objects.count()
        stats['lignes_commandes'] = LigneCommande.objects.count()
        stats['sessions_caisse'] = SessionCaisse.objects.count()
        stats['paiements'] = Paiement.objects.count()
        stats['mouvements_caisse'] = MouvementCaisse.objects.count()
        stats['transferts'] = TransfertCaisse.objects.count()
        stats['mouvements_stock'] = MouvementStock.objects.count()
        stats['stock_entrepots'] = StockEntrepot.objects.count()
        stats['ecritures_mvt'] = EcritureModel.objects.filter(reference__startswith='MVT-').count()

        # Dernier inventaire valide
        dernier_inventaire = Inventaire.objects.filter(statut='VALIDE').order_by('-date_fin').first()
        if not dernier_inventaire:
            dernier_inventaire = Inventaire.objects.filter(statut='TERMINE').order_by('-date_fin').first()

        # Afficher le résumé
        self.stdout.write("=" * 60)
        self.stdout.write("RÉINITIALISATION DES DONNÉES DE TEST")
        self.stdout.write("=" * 60)
        self.stdout.write("")
        self.stdout.write("Données à supprimer :")
        for key, val in stats.items():
            if val > 0:
                self.stdout.write(f"  {key}: {val}")
        self.stdout.write("")

        if dernier_inventaire:
            self.stdout.write(f"Inventaire de référence : {dernier_inventaire.code} ({dernier_inventaire.date_fin.date()})")
            ref_count = dernier_inventaire.lignes.count()
            self.stdout.write(f"  {ref_count} ligne(s) d'inventaire")
        else:
            self.stdout.write("Aucun inventaire VALIDE/TERMINE trouvé — le stock sera mis à 0")
        self.stdout.write("")

        if not self.apply:
            self.stdout.write("Ajoutez --apply pour exécuter le nettoyage.")
            self.stdout.write("Ajoutez --force pour éviter la confirmation.")
            return

        if not self.force:
            self.stdout.write("⚠️  CETTE ACTION EST IRRÉVERSIBLE ⚠️")
            reponse = input("Tapez 'YES' pour confirmer la suppression de toutes ces données : ")
            if reponse != 'YES':
                self.stderr.write("Annulé.")
                return

        if self.dry_run:
            self.stdout.write("🔷 Mode DRY RUN — aucune écriture réelle")
        else:
            self.stdout.write("🔴 Exécution du nettoyage...")

        # Ordre de suppression (respecter les FK)
        with transaction.atomic():
            # 1. Paiements (liés aux ventes/commandes)
            paiements = Paiement.objects.all()
            if not self.dry_run:
                paiements.delete()
            self.stdout.write(f"  ✓ Paiements supprimés ({stats['paiements']})")

            # 2. Mouvements de caisse
            mc = MouvementCaisse.objects.all()
            if not self.dry_run:
                mc.delete()
            self.stdout.write(f"  ✓ Mouvements caisse supprimés ({stats['mouvements_caisse']})")

            # 3. Transferts caisse
            tc = TransfertCaisse.objects.all()
            if not self.dry_run:
                tc.delete()
            self.stdout.write(f"  ✓ Transferts supprimés ({stats['transferts']})")

            # 4. Ventes
            ve = Vente.objects.all()
            if not self.dry_run:
                ve.delete()
            self.stdout.write(f"  ✓ Ventes supprimées ({stats['ventes']})")

            # 5. Lignes de commande (cascade depuis commande, mais explicite)
            lc = LigneCommande.objects.all()
            if not self.dry_run:
                lc.delete()
            self.stdout.write(f"  ✓ Lignes commande supprimées ({stats['lignes_commandes']})")

            # 6. Commandes
            co = Commande.objects.all()
            if not self.dry_run:
                co.delete()
            self.stdout.write(f"  ✓ Commandes supprimées ({stats['commandes']})")

            # 7. Sessions caisse
            sc = SessionCaisse.objects.all()
            if not self.dry_run:
                sc.delete()
            self.stdout.write(f"  ✓ Sessions caisse supprimées ({stats['sessions_caisse']})")

            # 8. Mouvements de stock
            ms = MouvementStock.objects.all()
            stock_mvt_count = ms.count()
            if not self.dry_run:
                ms.delete()
                # Reset auto-increment (compatible SQLite + PostgreSQL)
                engine = connection.vendor
                with connection.cursor() as cursor:
                    if engine == 'sqlite':
                        cursor.execute("DELETE FROM sqlite_sequence WHERE name='stock_mouvements'")
                    elif engine == 'postgresql':
                        cursor.execute("ALTER SEQUENCE stock_mouvements_id_seq RESTART WITH 1")
            self.stdout.write(f"  ✓ Mouvements stock supprimés ({stock_mvt_count})")

            # 9. Supprimer les écritures comptables orphelines (MVT-* sans mouvement lié)
            ecritures_mvt = EcritureModel.objects.filter(reference__startswith='MVT-')
            ec_count = ecritures_mvt.count()
            if not self.dry_run:
                LigneEcritureModel.objects.filter(ecriture__in=ecritures_mvt).delete()
                ecritures_mvt.delete()
            self.stdout.write(f"  ✓ Écritures comptables orphelines supprimées ({ec_count})")

            # 10. Réinitialiser les stocks
            if dernier_inventaire:
                for li in dernier_inventaire.lignes.select_related('produit').all():
                    entrepots = StockEntrepot.objects.filter(produit=li.produit)
                    if not self.dry_run:
                        if entrepots.exists():
                            # Prendre le premier entrepôt du produit
                            se = entrepots.first()
                            se.quantite = li.quantite_reelle
                            se.save(update_fields=['quantite'])
                        else:
                            # Créer un enregistrement de stock si inexistant
                            inv_entrepot = dernier_inventaire.entrepot
                            if inv_entrepot:
                                StockEntrepot.objects.create(
                                    entrepot=inv_entrepot,
                                    produit=li.produit,
                                    quantite=li.quantite_reelle,
                                )
                self.stdout.write(f"  ✓ Stock réinitialisé depuis l'inventaire '{dernier_inventaire.code}'")
            else:
                # Pas d'inventaire → stock à 0
                if not self.dry_run:
                    StockEntrepot.objects.all().update(quantite=0)
                self.stdout.write("  ✓ Stock mis à 0 (aucun inventaire de référence)")

            # 10. Réinitialiser les caisses
            caisses = Caisse.objects.all()
            if not self.dry_run:
                caisses.update(solde=0)
            self.stdout.write(f"  ✓ Soldes caisses remis à 0 ({caisses.count()})")

        self.stdout.write("")
        self.stdout.write("=" * 60)
        self.stdout.write("✅ NETTOYAGE TERMINÉ")
        self.stdout.write("=" * 60)

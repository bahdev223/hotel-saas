"""
Contrôle d'intégrité du moteur de stock (lecture seule).

Détecte les incohérences sans jamais modifier les données :
- stocks négatifs
- lots à quantité restante négative
- mouvements sans journal
- mouvements sans source d'opération
- lignes de journal incohérentes (stock_avant + mouvement != stock_apres)
- stock d'un produit != somme des lots restants (produits gérés en lots)
- transferts incomplets (une seule direction pour une même source)

Warnings métier (non bloquants) :
- lots périmés avec quantité restante > 0

Usage :
    python manage.py verifier_stock
    python manage.py verifier_stock --strict   # code retour 1 si anomalie
"""
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db.models import Sum

from apps.stock.models import StockEntrepot, Lot, MouvementStock
from apps.stock.enums.mouvements import TypeMouvement

TOLERANCE = Decimal("0.01")


class Command(BaseCommand):
    help = "Contrôle d'intégrité du stock (lecture seule)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Retourne un code de sortie 1 si au moins une anomalie est détectée.",
        )

    def handle(self, *args, **options):
        anomalies = []
        warnings = []

        anomalies += self._stocks_negatifs()
        anomalies += self._lots_negatifs()
        anomalies += self._mouvements_sans_journal()
        anomalies += self._mouvements_sans_source()
        anomalies += self._journal_incoherent()
        anomalies += self._stock_vs_lots()
        anomalies += self._transferts_incomplets()

        warnings += self._lots_perimes()

        self._afficher(anomalies, warnings)

        if options["strict"] and anomalies:
            raise SystemExit(1)

    # ------------------------------------------------------------------ checks

    def _stocks_negatifs(self):
        qs = StockEntrepot.objects.filter(quantite__lt=0).select_related("produit", "entrepot")
        return [
            f"Stock négatif : {s.produit.nom} / {s.entrepot.nom} = {s.quantite}"
            for s in qs
        ]

    def _lots_negatifs(self):
        qs = Lot.objects.filter(quantite_restante__lt=0).select_related("produit")
        return [
            f"Lot négatif : lot {lot.numero} / {lot.produit.nom} = {lot.quantite_restante}"
            for lot in qs
        ]

    def _mouvements_sans_journal(self):
        qs = MouvementStock.objects.filter(journal__isnull=True).select_related("produit")
        return [
            f"Mouvement #{m.id} ({m.produit.nom}, {m.type_mouvement}) : journal absent"
            for m in qs
        ]

    def _mouvements_sans_source(self):
        qs = MouvementStock.objects.filter(source_operation__isnull=True).select_related("produit")
        return [
            f"Mouvement #{m.id} ({m.produit.nom}, {m.type_mouvement}) : source d'opération absente"
            for m in qs
        ]

    def _journal_incoherent(self):
        anomalies = []
        # stock_avant + quantite_mouvement doit égaler stock_apres
        from apps.stock.models import JournalStock
        for j in JournalStock.objects.select_related("produit", "entrepot").iterator():
            attendu = j.stock_avant + j.quantite_mouvement
            if abs(attendu - j.stock_apres) > TOLERANCE:
                anomalies.append(
                    f"Journal #{j.id} ({j.produit.nom}) : {j.stock_avant} + ({j.quantite_mouvement}) "
                    f"= {attendu} != stock_apres {j.stock_apres}"
                )
        return anomalies

    def _stock_vs_lots(self):
        """Pour les produits gérés en lots : stock total (tous entrepôts) vs somme des lots restants."""
        anomalies = []
        produit_ids = Lot.objects.values_list("produit_id", flat=True).distinct()
        for produit_id in produit_ids:
            total_stock = (
                StockEntrepot.objects.filter(produit_id=produit_id)
                .aggregate(t=Sum("quantite"))["t"] or Decimal("0")
            )
            total_lots = (
                Lot.objects.filter(produit_id=produit_id, actif=True)
                .aggregate(t=Sum("quantite_restante"))["t"] or Decimal("0")
            )
            if abs(total_stock - total_lots) > TOLERANCE:
                from apps.stock.models import Produit
                nom = Produit.objects.filter(pk=produit_id).values_list("nom", flat=True).first() or produit_id
                anomalies.append(
                    f"Écart stock/lots : {nom} -stock {total_stock} != somme lots {total_lots}"
                )
        return anomalies

    def _transferts_incomplets(self):
        """Une source de transfert doit avoir une sortie ET une entrée."""
        anomalies = []
        transferts = (
            MouvementStock.objects.filter(
                type_mouvement__in=[TypeMouvement.TRANSFERT_SORTIE, TypeMouvement.TRANSFERT_ENTREE],
                source_operation__isnull=False,
            )
            .values("source_operation_id", "type_mouvement")
        )
        par_source = {}
        for row in transferts:
            par_source.setdefault(row["source_operation_id"], set()).add(row["type_mouvement"])
        for source_id, directions in par_source.items():
            if directions != {TypeMouvement.TRANSFERT_SORTIE, TypeMouvement.TRANSFERT_ENTREE}:
                presente = ", ".join(sorted(directions))
                anomalies.append(
                    f"Transfert incomplet : source #{source_id} -direction(s) présente(s) : {presente}"
                )
        return anomalies

    def _lots_perimes(self):
        from datetime import date
        qs = Lot.objects.filter(
            actif=True,
            quantite_restante__gt=0,
            date_peremption__lt=date.today(),
        ).select_related("produit")
        return [
            f"Lot périmé avec stock : {lot.numero} / {lot.produit.nom} "
            f"= {lot.quantite_restante} (péremption {lot.date_peremption})"
            for lot in qs
        ]

    # ------------------------------------------------------------------ output

    def _afficher(self, anomalies, warnings):
        if not anomalies and not warnings:
            self.stdout.write(self.style.SUCCESS("[OK] Aucun probleme detecte : le stock est coherent."))
            return

        if anomalies:
            self.stdout.write(self.style.ERROR(f"\n[X] {len(anomalies)} anomalie(s) detectee(s) :"))
            for a in anomalies:
                self.stdout.write(self.style.ERROR(f"  - {a}"))

        if warnings:
            self.stdout.write(self.style.WARNING(f"\n[!] {len(warnings)} avertissement(s) :"))
            for w in warnings:
                self.stdout.write(self.style.WARNING(f"  - {w}"))

        if not anomalies:
            self.stdout.write(self.style.SUCCESS("\n[OK] Aucune anomalie d'integrite (seulement des avertissements)."))

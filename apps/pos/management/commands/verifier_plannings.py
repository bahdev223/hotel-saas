from django.core.management.base import BaseCommand
from datetime import timedelta

from apps.pos.models import ShiftEmploye, AffectationPointVente
from django.db.models import Q


class Command(BaseCommand):
    help = "D\u00e9tecte les chevauchements de shifts existants (m\u00eame PV ou m\u00eame employ\u00e9)"

    def add_arguments(self, parser):
        parser.add_argument('--jours', type=int, default=30,
                            help="Fen\u00eatre d'analyse en jours autour d'aujourd'hui (d\u00e9faut 30)")

    def handle(self, *args, **options):
        from django.utils import timezone
        jours = options['jours']
        today = timezone.localdate()

        shifts = ShiftEmploye.objects.filter(
            affectation__isnull=False,
        ).exclude(statut='ANNULE').select_related(
            'affectation__employe', 'affectation__point_vente'
        ).order_by('debut_prevu')

        shifts = [s for s in shifts if s.debut_prevu and s.fin_prevue and
                  s.debut_prevu.date() >= today - timedelta(days=jours) and
                  s.debut_prevu.date() <= today + timedelta(days=jours)]

        conflits = []
        for i, a in enumerate(shifts):
            a_deb, a_fin = a.debut_prevu, a.fin_prevue
            for b in shifts[i + 1:]:
                if not b.debut_prevu:
                    continue
                if b.debut_prevu.date() > a_deb.date() + timedelta(days=1):
                    break
                meme_employe = a.affectation.employe_id == b.affectation.employe_id
                meme_pv = a.affectation.point_vente_id == b.affectation.point_vente_id
                if not (meme_employe or meme_pv):
                    continue
                if a_deb < b.fin_prevue and b.debut_prevu < a_fin:
                    raison = "m\u00eame employ\u00e9" if meme_employe else "m\u00eame point de vente"
                    conflits.append((a, b, raison))

        if not conflits:
            self.stdout.write(self.style.SUCCESS(f"Aucun chevauchement sur \u00b1{jours} jours."))
            return

        self.stdout.write(self.style.ERROR(f"{len(conflits)} chevauchement(s) d\u00e9tect\u00e9(s) :\n"))
        for a, b, raison in conflits:
            emp_a = a.affectation.employe.nom_complet
            pv_a = a.affectation.point_vente.code
            emp_b = b.affectation.employe.nom_complet
            pv_b = b.affectation.point_vente.code
            self.stdout.write(
                f"  [{raison}] #{a.id} {emp_a} @ {pv_a} "
                f"{a.debut_prevu}-{a.fin_prevue} ({a.statut})\n"
                f"        <-> #{b.id} {emp_b} @ {pv_b} "
                f"{b.debut_prevu}-{b.fin_prevue} ({b.statut})\n"
            )
        self.stdout.write("Corrigez via la page Planning (modifier/supprimer les doublons).")

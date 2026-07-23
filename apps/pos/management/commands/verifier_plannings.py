# python manage.py verifier_plannings
# Liste les plannings qui se chevauchent (même employé sur deux PV,
# ou deux employés sur le même PV au même moment).
from django.core.management.base import BaseCommand
from datetime import timedelta

from apps.pos.models import SessionPlanning
from apps.pos.views.planning import _intervalle_planning


class Command(BaseCommand):
    help = "Détecte les chevauchements de plannings existants (même PV ou même employé)"

    def add_arguments(self, parser):
        parser.add_argument('--jours', type=int, default=30,
                            help="Fenêtre d'analyse en jours autour d'aujourd'hui (défaut 30)")

    def handle(self, *args, **options):
        from django.utils import timezone
        jours = options['jours']
        today = timezone.localdate()
        qs = SessionPlanning.objects.filter(
            date__gte=today - timedelta(days=jours),
            date__lte=today + timedelta(days=jours),
        ).exclude(statut='ANNULE').select_related('employe', 'point_vente').order_by('date', 'heure_debut')

        plannings = list(qs)
        conflits = []
        for i, a in enumerate(plannings):
            a_deb, a_fin = _intervalle_planning(a.date, a.heure_debut, a.heure_fin)
            for b in plannings[i + 1:]:
                if b.date > a.date + timedelta(days=1):
                    break
                meme_employe = a.employe_id == b.employe_id
                meme_pv = a.point_vente_id == b.point_vente_id
                if not (meme_employe or meme_pv):
                    continue
                b_deb, b_fin = _intervalle_planning(b.date, b.heure_debut, b.heure_fin)
                if a_deb < b_fin and b_deb < a_fin:
                    raison = "même employé" if meme_employe else "même point de vente"
                    conflits.append((a, b, raison))

        if not conflits:
            self.stdout.write(self.style.SUCCESS(f"Aucun chevauchement sur ±{jours} jours."))
            return

        self.stdout.write(self.style.ERROR(f"{len(conflits)} chevauchement(s) détecté(s) :\n"))
        for a, b, raison in conflits:
            self.stdout.write(
                f"  [{raison}] #{a.id} {a.employe.nom_complet} @ {a.point_vente.code} "
                f"{a.date} {a.heure_debut}-{a.heure_fin} ({a.statut})\n"
                f"        <-> #{b.id} {b.employe.nom_complet} @ {b.point_vente.code} "
                f"{b.date} {b.heure_debut}-{b.heure_fin} ({b.statut})\n"
            )
        self.stdout.write("Corrigez via la page Planning (modifier/supprimer les doublons).")

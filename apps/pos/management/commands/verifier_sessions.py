"""
Management commande : Vérifier et corriger les incohérences des sessions de caisse.

Usage:
    python manage.py verifier_sessions                    # Read-only, affiche les anomalies
    python manage.py verifier_sessions --fix              # Applique les corrections
    python manage.py verifier_sessions --fix --dry-run    # Simule sans écrire
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from django.db import transaction
from datetime import datetime, timedelta
from collections import defaultdict


class Command(BaseCommand):
    help = "Vérifie et corrige les incohérences des sessions de caisse"

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Appliquer les corrections')
        parser.add_argument('--dry-run', action='store_true', help='Simuler sans écrire')

    def handle(self, *args, **options):
        self.fix = options['fix']
        self.dry_run = options['dry_run']

        if self.dry_run and not self.fix:
            self.stderr.write("--dry-run sans --fix n'a pas de sens, ignore --dry-run")

        self.anomalies = []
        self.corrections = []

        self.stdout.write("=" * 60)
        self.stdout.write("VÉRIFICATION DES SESSIONS DE CAISSE")
        if self.fix:
            self.stdout.write(f"Mode: {'SIMULATION (--dry-run)' if self.dry_run else 'CORRECTION (--fix)'}")
        else:
            self.stdout.write("Mode: LECTURE SEULE (ajoutez --fix pour corriger)")
        self.stdout.write("=" * 60)

        from apps.pos.models import SessionCaisse, SessionPlanning, Vente
        from apps.pos.services.caisse_session_service import CaisseSessionService

        now = timezone.localtime()

        # ─── 1. Sessions OUVERTE avec planning expiré ───
        self._checker_planning_expire(now)

        # ─── 2. Sessions OUVERTE > 24h sans planning ───
        self._checker_session_orpheline(now)

        # ─── 3. Multiples sessions OUVERTE sur même caisse ───
        self._checker_multi_sessions()

        # ─── 4. Planning PLANIFIE/CONFIRME avec session fermée ───
        self._checker_planning_non_effectue()

        # ─── 5. Sessions avec planning_id=NULL mais debut_prevu/fin_prevu ───
        self._checker_planning_fk_manquant()

        # ─── Bilan ───
        self.stdout.write("=" * 60)
        total = len(self.anomalies)
        corrigees = len([a for a in self.anomalies if a.get('corrigee')])
        non_corrigees = total - corrigees
        self.stdout.write(f"Anomalies détectées : {total}")
        if self.fix:
            self.stdout.write(f"Corrigées          : {corrigees}")
            if non_corrigees:
                self.stdout.write(f"Non corrigées      : {non_corrigees} (vérifier manuellement)")
            if self.dry_run:
                self.stdout.write(self.style.WARNING("⚠  Simulation uniquement — aucune écriture réelle"))
        self.stdout.write("=" * 60)

    # ─── Helpers ───

    def _log_anomalie(self, session, type_anomalie, message, corrigeable=True):
        entry = {
            'session_id': session.id,
            'statut': session.statut,
            'point_vente': str(session.point_vente) if session.point_vente else 'N/A',
            'type': type_anomalie,
            'message': message,
            'corrigeable': corrigeable,
            'corrigee': False,
        }
        self.anomalies.append(entry)
        self.stdout.write(f"  [{type_anomalie}] Session #{session.id} ({session.point_vente or '?'}) — {message}")

    def _corriger(self, entry, action):
        entry['corrigee'] = True
        self.corrections.append(action)
        self.stdout.write(f"         → {action}")

    def _apply(self, savecallback):
        if self.fix and not self.dry_run:
            savecallback()

    # ─── Check 1: Sessions OUVERTE avec planning expiré ───

    def _checker_planning_expire(self, now):
        from apps.pos.models import SessionCaisse
        sessions = SessionCaisse.objects.filter(statut='OUVERTE', planning__isnull=False).select_related('planning', 'point_vente')

        for s in sessions:
            p = s.planning
            termine = False

            if p.heure_debut == p.heure_fin:
                continue
            elif p.heure_debut < p.heure_fin:
                fin = datetime.combine(p.date, p.heure_fin)
                fin = timezone.make_aware(fin, timezone.get_current_timezone())
                if now > fin:
                    termine = True
            else:
                fin = datetime.combine(p.date + timedelta(days=1), p.heure_fin)
                fin = timezone.make_aware(fin, timezone.get_current_timezone())
                if now > fin:
                    termine = True

            if not termine:
                continue

            entry = self._log_anomalie(
                s, 'PLANNING_EXPIRE',
                f"Session ouverte mais planning terminé ({p.date} {p.heure_debut}-{p.heure_fin})"
            )

            from apps.pos.services.caisse_session_service import CaisseSessionService
            caissier = s.caissier_ouverture

            def fix():
                CaisseSessionService.fermeture_automatique(s, caissier)
            self._apply(fix)
            self._corriger(entry, f"Fermeture automatique (solde_attendu={s.solde_attendu:.0f} F)")

    # ─── Check 2: Sessions OUVERTE > 24h sans planning ───

    def _checker_session_orpheline(self, now):
        from apps.pos.models import SessionCaisse
        sessions = SessionCaisse.objects.filter(statut='OUVERTE', planning__isnull=True).select_related('point_vente')

        for s in sessions:
            if s.date_ouverture and (now - s.date_ouverture) > timedelta(hours=24):
                entry = self._log_anomalie(
                    s, 'SESSION_ORPHELINE',
                    f"Session ouverte depuis >24h sans planning ({s.date_ouverture.strftime('%d/%m/%Y %H:%M')})"
                )

                def fix():
                    s.statut = 'SUSPENDUE'
                    s.save(update_fields=['statut'])
                self._apply(fix)
                self._corriger(entry, "Session suspendue")

    # ─── Check 3: Multiples sessions OUVERTE sur même caisse ───

    def _checker_multi_sessions(self):
        from apps.pos.models import SessionCaisse
        sessions = SessionCaisse.objects.filter(statut='OUVERTE').select_related('caisse', 'point_vente').order_by('-date_ouverture')

        par_caisse = defaultdict(list)
        for s in sessions:
            par_caisse[s.caisse_id].append(s)

        for caisse_id, s_list in par_caisse.items():
            if len(s_list) <= 1:
                continue
            # Garder la plus récente ouverte, fermer/suspendre les autres
            plus_recente = s_list[0]
            for s in s_list[1:]:
                entry = self._log_anomalie(
                    s, 'MULTI_SESSION',
                    f"Session ouverte sur la même caisse #{caisse_id} alors que #{plus_recente.id} est également ouverte"
                )

                def fix(sess=s):
                    sess.statut = 'SUSPENDUE'
                    sess.save(update_fields=['statut'])
                self._apply(fix)
                self._corriger(entry, "Session suspendue (conflit)")

    # ─── Check 4: Planning PLANIFIE/CONFIRME avec session FERMEE ───

    def _checker_planning_non_effectue(self):
        from apps.pos.models import SessionCaisse, SessionPlanning
        sessions_fermees = SessionCaisse.objects.filter(
            statut='FERMEE', planning__isnull=False
        ).select_related('planning')

        for s in sessions_fermees:
            p = s.planning
            if p.statut in ('PLANIFIE', 'CONFIRME'):
                entry = self._log_anomalie(
                    s, 'PLANNING_NON_EFFECTUE',
                    f"Session fermée mais planning toujours {p.statut} ({p.date} {p.heure_debut}-{p.heure_fin})"
                )

                def fix():
                    p.statut = 'EFFECTUE'
                    p.save(update_fields=['statut'])
                self._apply(fix)
                self._corriger(entry, "Planning passé à EFFECTUE")

    # ─── Check 5: Planning FK manquant ───

    def _checker_planning_fk_manquant(self):
        from apps.pos.models import SessionCaisse, SessionPlanning
        sessions = SessionCaisse.objects.filter(
            planning__isnull=True,
            debut_prevu__isnull=False,
        ).select_related('point_vente')

        for s in sessions:
            if not s.point_vente or not s.caissier_ouverture:
                continue
            # Chercher un planning correspondant par date/heure
            date_ouv = s.date_ouverture.date() if s.date_ouverture else None
            if not date_ouv:
                continue

            plannings = SessionPlanning.objects.filter(
                employe=s.caissier_ouverture,
                point_vente=s.point_vente,
                date=date_ouv,
                heure_debut=s.debut_prevu,
            ).exclude(statut='ANNULE')

            p = plannings.first()
            if p:
                entry = self._log_anomalie(
                    s, 'PLANNING_FK_MANQUANT',
                    f"Planning FK null mais planning correspondant trouvé #{p.id}"
                )

                def fix():
                    s.planning = p
                    s.save(update_fields=['planning'])
                self._apply(fix)
                self._corriger(entry, "Planning FK rattaché")

        # Vérifier aussi debut_prevu/fin_prevu sans planning du tout
        sessions_sans_planning = SessionCaisse.objects.filter(
            planning__isnull=True,
            point_vente__isnull=False,
        ).select_related('point_vente')

        for s in sessions_sans_planning:
            if not s.caissier_ouverture:
                continue
            date_ouv = s.date_ouverture.date() if s.date_ouverture else None
            if not date_ouv:
                continue

            plannings = SessionPlanning.objects.filter(
                employe=s.caissier_ouverture,
                point_vente=s.point_vente,
                date=date_ouv,
            ).exclude(statut='ANNULE').order_by('heure_debut')

            p = plannings.first()
            if p and not s.planning:
                entry = self._log_anomalie(
                    s, 'PLANNING_FK_MANQUANT',
                    f"Planning FK null mais planning #{p.id} existe pour cette date"
                )

                def fix():
                    s.planning = p
                    if not s.debut_prevu:
                        s.debut_prevu = p.heure_debut
                    if not s.fin_prevu:
                        s.fin_prevu = p.heure_fin
                    s.save(update_fields=['planning', 'debut_prevu', 'fin_prevu'])
                self._apply(fix)
                self._corriger(entry, f"Planning #{p.id} rattaché, horaires mis à jour")

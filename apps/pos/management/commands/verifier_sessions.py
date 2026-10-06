"""
Management commande : V\u00e9rifier et corriger les incoh\u00e9rences des sessions de caisse.

Usage:
    python manage.py verifier_sessions                    # Read-only, affiche les anomalies
    python manage.py verifier_sessions --fix              # Applique les corrections
    python manage.py verifier_sessions --fix --dry-run    # Simule sans \u00e9crire
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict


class Command(BaseCommand):
    help = "V\u00e9rifie et corrige les incoh\u00e9rences des sessions de caisse"

    def add_arguments(self, parser):
        parser.add_argument('--fix', action='store_true', help='Appliquer les corrections')
        parser.add_argument('--dry-run', action='store_true', help='Simuler sans \u00e9crire')

    def handle(self, *args, **options):
        self.fix = options['fix']
        self.dry_run = options['dry_run']

        if self.dry_run and not self.fix:
            self.stderr.write("--dry-run sans --fix n'a pas de sens, ignore --dry-run")

        self.anomalies = []
        self.corrections = []

        self.stdout.write("=" * 60)
        self.stdout.write("V\u00c9RIFICATION DES SESSIONS DE CAISSE")
        if self.fix:
            self.stdout.write(f"Mode: {'SIMULATION (--dry-run)' if self.dry_run else 'CORRECTION (--fix)'}")
        else:
            self.stdout.write("Mode: LECTURE SEULE (ajoutez --fix pour corriger)")
        self.stdout.write("=" * 60)

        from apps.pos.models import SessionCaisse
        from apps.pos.services.caisse_session_service import CaisseSessionService

        now = timezone.localtime()

        # 1. Accès POS expiré/révoqué pendant une session ouverte.
        self._checker_acces_expire(now)

        # 2. Passations dont la fenêtre de grâce est terminée.
        self._checker_passations_expirees(now)

        # 3. Sessions non finalisées > 24h.
        self._checker_session_orpheline(now)

        # 4. Multiples sessions non finalisées sur même caisse.
        self._checker_multi_sessions()

        # Bilan
        self.stdout.write("=" * 60)
        total = len(self.anomalies)
        corrigees = len([a for a in self.anomalies if a.get('corrigee')])
        non_corrigees = total - corrigees
        self.stdout.write(f"Anomalies d\u00e9tect\u00e9es : {total}")
        if self.fix:
            self.stdout.write(f"Corrig\u00e9es          : {corrigees}")
            if non_corrigees:
                self.stdout.write(f"Non corrig\u00e9es      : {non_corrigees} (v\u00e9rifier manuellement)")
            if self.dry_run:
                self.stdout.write(self.style.WARNING("\u26a0  Simulation uniquement \u2014 aucune \u00e9criture r\u00e9elle"))
        self.stdout.write("=" * 60)

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
        self.stdout.write(f"  [{type_anomalie}] Session #{session.id} ({session.point_vente or '?'}) \u2014 {message}")

        return entry

    def _corriger(self, entry, action):
        entry['corrigee'] = True
        self.corrections.append(action)
        self.stdout.write(f"         \u2192 {action}")

    def _apply(self, savecallback):
        if self.fix and not self.dry_run:
            savecallback()

    def _checker_acces_expire(self, now):
        from apps.pos.constants import ActionPOS, POINTS_VENTE_OPERATIONNELS
        from apps.pos.models import SessionCaisse
        from apps.pos.services.access_service import POSAccessService

        sessions = (
            SessionCaisse.objects
            .filter(
                statut='OUVERTE',
                point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
            )
            .select_related('point_vente', 'ouverte_par', 'ouverte_par__user')
        )

        for session in sessions:
            employe = session.ouverte_par
            if employe is None:
                continue

            decision = POSAccessService.check(
                user=employe.user,
                employe=employe,
                point_vente=session.point_vente,
                action=ActionPOS.ENCAISSER,
                moment=now,
            )
            if decision.allowed:
                continue

            entry = self._log_anomalie(
                session,
                'ACCES_CAISSE_EXPIRE',
                f"Droit d'encaisser non valide ({decision.reason}) — passation requise",
            )

            def fix(sess=session, reason=decision.reason):
                CaisseSessionService.demarrer_passation(
                    sess,
                    motif=f"Droit caisse expiré/révoqué: {reason}",
                    moment=now,
                )

            self._apply(fix)
            self._corriger(entry, "Session passée en EN_PASSATION")

    def _checker_passations_expirees(self, now):
        from apps.pos.models import SessionCaisse

        sessions = SessionCaisse.objects.filter(
            statut='EN_PASSATION',
            passation_jusqua__isnull=False,
            passation_jusqua__lt=now,
        ).select_related('point_vente')

        for session in sessions:
            entry = self._log_anomalie(
                session,
                'PASSATION_EXPIREE',
                "Fenêtre de passation terminée — comptage requis",
            )

            def fix(sess=session):
                sess.statut = 'EN_COMPTAGE'
                suffix = "Fenêtre de passation expirée"
                sess.notes = f"{sess.notes} | {suffix}" if sess.notes else suffix
                sess.save(update_fields=['statut', 'notes'])

            self._apply(fix)
            self._corriger(entry, "Session passée en EN_COMPTAGE")

    def _checker_session_orpheline(self, now):
        from apps.pos.models import SessionCaisse
        sessions = SessionCaisse.objects.filter(
            statut__in=('OUVERTE', 'EN_PASSATION', 'EN_COMPTAGE')
        ).select_related('point_vente')

        for s in sessions:
            if s.date_ouverture and (now - s.date_ouverture) > timedelta(hours=24):
                entry = self._log_anomalie(
                    s, 'SESSION_ORPHELINE',
                    f"Session ouverte depuis >24h ({s.date_ouverture.strftime('%d/%m/%Y %H:%M')})"
                )

                def fix():
                    s.statut = 'EN_COMPTAGE'
                    s.save(update_fields=['statut'])
                self._apply(fix)
                self._corriger(entry, "Session passée en EN_COMPTAGE")

    def _checker_multi_sessions(self):
        from apps.pos.models import SessionCaisse
        sessions = SessionCaisse.objects.filter(
            statut__in=('OUVERTE', 'EN_PASSATION', 'EN_COMPTAGE')
        ).select_related('caisse', 'point_vente').order_by('-date_ouverture')

        par_caisse = defaultdict(list)
        for s in sessions:
            par_caisse[s.caisse_id].append(s)

        for caisse_id, s_list in par_caisse.items():
            if len(s_list) <= 1:
                continue
            plus_recente = s_list[0]
            for s in s_list[1:]:
                entry = self._log_anomalie(
                    s, 'MULTI_SESSION',
                    f"Session ouverte sur la m\u00eame caisse #{caisse_id} alors que #{plus_recente.id} est \u00e9galement ouverte"
                )

                def fix(sess=s):
                    sess.statut = 'EN_COMPTAGE'
                    sess.notes = (
                        f"{sess.notes} | Conflit multi-session"
                        if sess.notes else "Conflit multi-session"
                    )
                    sess.save(update_fields=['statut', 'notes'])
                self._apply(fix)
                self._corriger(entry, "Session passée en EN_COMPTAGE (conflit)")

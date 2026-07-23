import os
import socket
import sys
import threading
import logging
from datetime import timedelta
from django.apps import AppConfig

_verifier_loop_started = False
_verifier_loop_lock = threading.Lock()

INTERVALLE_SECONDES = 120
VERROU_PERIME_APRES = timedelta(seconds=INTERVALLE_SECONDES * 3)

logger = logging.getLogger('pos.verifier_loop')
if not logger.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter('[%(asctime)s] %(name)s %(levelname)s: %(message)s'))
    logger.addHandler(_handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def _identifiant_worker():
    return f"{socket.gethostname()}:{os.getpid()}"


def _tenter_acquerir_verrou(identifiant):
    """Verrou distribue en base : renvoie True si CE worker detient le verrou
    pour ce cycle (l'a acquis pour la premiere fois, l'a deja, ou l'a repris
    parce que le detenteur precedent n'a plus donne signe de vie).
    Une seule requete UPDATE atomique -> pas de race condition possible,
    fonctionne pareil sur SQLite (local) et Postgres (production)."""
    from django.db.models import Q
    from django.utils import timezone
    from apps.pos.models import VerifierLoopLock

    VerifierLoopLock.objects.get_or_create(cle='session_verifier')
    now = timezone.now()
    seuil_perime = now - VERROU_PERIME_APRES

    maj = VerifierLoopLock.objects.filter(cle='session_verifier').filter(
        Q(detenteur=identifiant) | Q(heartbeat__isnull=True) | Q(heartbeat__lt=seuil_perime)
    ).update(detenteur=identifiant, heartbeat=now)

    return maj > 0


def _resume_anomalies(anomalies):
    """Compte les anomalies par type pour un log de synthese lisible."""
    par_type = {}
    corrigees = 0
    for a in anomalies:
        par_type[a['type']] = par_type.get(a['type'], 0) + 1
        if a.get('corrigee'):
            corrigees += 1
    detail = ', '.join(f"{t}={n}" for t, n in par_type.items()) if par_type else 'aucune'
    return len(anomalies), corrigees, detail


def _executer_cycle():
    """Un cycle de verification, avec logs structures. Instancie la commande
    directement (plutot que call_command) pour recuperer les compteurs."""
    from apps.pos.management.commands.verifier_sessions import Command as VerifierCommand

    cmd = VerifierCommand()
    cmd.handle(fix=True, dry_run=False)
    total, corrigees, detail = _resume_anomalies(cmd.anomalies)
    if total:
        logger.info(f"cycle termine — anomalies={total} corrigees={corrigees} ({detail})")
    else:
        logger.info("cycle termine — aucune anomalie")


def _demarrer_verifier_loop():
    """Lance la boucle de verification des sessions en tache de fond, pour la
    duree de vie du processus. Idempotent au niveau du process (ne demarre
    qu'un thread par processus) ET protege au niveau base de donnees (un seul
    worker/instance execute reellement le travail a un instant donne, via
    VerifierLoopLock -- voir _tenter_acquerir_verrou)."""
    global _verifier_loop_started
    with _verifier_loop_lock:
        if _verifier_loop_started:
            return
        _verifier_loop_started = True

    identifiant = _identifiant_worker()

    def boucle():
        import time

        time.sleep(30)  # laisser le temps a la DB/aux migrations de finir
        logger.info(
            f"demarre — identifiant={identifiant} interval={INTERVALLE_SECONDES}s "
            f"verrou_perime_apres={VERROU_PERIME_APRES.total_seconds():.0f}s"
        )
        while True:
            try:
                if _tenter_acquerir_verrou(identifiant):
                    _executer_cycle()
                else:
                    logger.debug(f"verrou detenu par un autre worker, cycle ignore ({identifiant})")
            except Exception:
                logger.exception(f"cycle en echec ({identifiant})")
            time.sleep(INTERVALLE_SECONDES)

    threading.Thread(target=boucle, daemon=True, name='session-verifier-loop').start()


class PosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.pos'

    def ready(self):
        # Ne demarrer la boucle de verification des sessions QUE quand l'app est
        # servie via WSGI (gunicorn) -- jamais pendant manage.py migrate/shell/
        # test/collectstatic/run_verifier_loop/etc, qui declenchent aussi ready().
        argv0 = os.path.basename(sys.argv[0]) if sys.argv else ''
        if argv0 == 'manage.py':
            return
        if os.environ.get('DISABLE_SESSION_VERIFIER_LOOP'):
            return
        _demarrer_verifier_loop()

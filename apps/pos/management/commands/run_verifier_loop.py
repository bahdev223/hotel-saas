import time
import logging
from django.core.management.base import BaseCommand
from django.core.management import call_command

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Boucle continue : lance verifier_sessions --fix toutes les 2 minutes'

    def handle(self, *args, **options):
        interval = 120
        self.stdout.write(f'[VERIFIER LOOP] Démarré — interval={interval}s')
        self.stdout.write(f'[VERIFIER LOOP] Ctrl+C pour arrêter')

        while True:
            try:
                self.stdout.write(f'[{time.strftime("%H:%M:%S")}] Exécution verifier_sessions --fix...')
                call_command('verifier_sessions', fix=True, dry_run=False)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f'Erreur: {e}'))
            time.sleep(interval)

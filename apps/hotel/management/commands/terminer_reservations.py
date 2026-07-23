from django.core.management.base import BaseCommand
from django.utils import timezone
from apps.hotel.models import LocationModel


class Command(BaseCommand):
    help = "Passe automatiquement les réservations CONFIRMEE en TERMINEE quand date_fin < now"

    def handle(self, *args, **options):
        now = timezone.localtime()
        qs = LocationModel.objects.filter(statut='CONFIRMEE', date_fin__lt=now)
        count = qs.count()
        for loc in qs:
            loc.terminer_auto()
        self.stdout.write(self.style.SUCCESS(f"{count} réservation(s) terminée(s) automatiquement"))

from django.db.models import Sum, Count
from apps.core.models import JourneeExploitation
from apps.hotel.models import ReservationModel

class HotelReportingService:
    @staticmethod
    def get_rapport_journalier(journee_exploitation):
        """
        Calcule les KPIs de l'hôtel pour une journée d'exploitation donnée.
        """
        # Pour une version V1, on compte simplement les réservations actives pendant cette date.
        # Idéalement, il faut lier les factures/séjours à la JourneeExploitation.
        date_metier = journee_exploitation.date_metier
        
        reservations_actives = ReservationModel.objects.filter(
            date_arrivee__lte=date_metier,
            date_depart__gt=date_metier,
            statut__in=['CONFIRMEE', 'EN_SEJOUR']
        )
        
        chambres_occupees = reservations_actives.count()
        total_chambres = 20  # À récupérer de ChambreModel.objects.filter(actif=True).count() idéalement
        
        return {
            'chambres_occupees': chambres_occupees,
            'taux_occupation': (chambres_occupees / total_chambres * 100) if total_chambres > 0 else 0,
            'reservations_actives': chambres_occupees
        }

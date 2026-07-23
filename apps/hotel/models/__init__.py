from apps.clients.models import Client
from .unite import UniteModel
from .location import LocationModel
from .types_chambres import TypeChambre
from .tarifs import TypeTarif, PlanTarifaire, TarifChambre, CreneauTarifaire
from .reservations import Reservation, ReservationChambre
from .sejours import Sejour
from .occupants import Occupant
from .services_sejour import ServiceSejour
from .historique import HistoriqueStatutChambre

ClientModel = Client  # backward compatibility alias

__all__ = [
    'ClientModel', 'Client',
    'UniteModel', 'LocationModel',
    'TypeChambre',
    'TypeTarif', 'PlanTarifaire', 'TarifChambre', 'CreneauTarifaire',
    'Reservation', 'ReservationChambre',
    'Sejour',
    'Occupant',
    'ServiceSejour',
    'HistoriqueStatutChambre',
]
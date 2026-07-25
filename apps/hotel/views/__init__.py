# apps/hotel/views/__init__.py
from .dashboard import dashboard
from .unites import (
    liste_unites,
    detail_unite,
    ajouter_unite,
    modifier_unite,
    changer_statut_unite,
)
from .reservations import (
    liste_reservations,
    detail_reservation,
    ajouter_reservation,
    annuler_reservation,
)
from .sejours import (
    liste_sejours,
    detail_sejour,
    check_in,
    check_out,
    cloturer_sejour,
)
from .api import (
    api_ca_evolution,
    api_save_unite,
    api_stats,
    api_supprimer_unite,
    api_unites,
    api_tarifs,
    api_save_tarif,
    api_supprimer_tarif,
)

__all__ = [
    'dashboard',
    'liste_unites',
    'detail_unite',
    'ajouter_unite',
    'modifier_unite',
    'changer_statut_unite',
    'api_ca_evolution',
    'api_save_unite',
    'api_stats',
    'api_supprimer_unite',
    'api_unites',
    'api_tarifs',
    'api_save_tarif',
    'api_supprimer_tarif',
    'liste_reservations',
    'detail_reservation',
    'ajouter_reservation',
    'annuler_reservation',
    'liste_sejours',
    'detail_sejour',
    'check_in',
    'check_out',
    'cloturer_sejour',
]

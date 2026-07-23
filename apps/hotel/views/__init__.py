# apps/hotel/views/__init__.py
from .dashboard import dashboard
from .clients import (
    liste_clients,
    detail_client,
    ajouter_client,
    modifier_client,
)
from .unites import (
    liste_unites,
    detail_unite,
    ajouter_unite,
    modifier_unite,
    changer_statut_unite,
)
from .locations import (
    liste_locations,
    detail_location,
    ajouter_sejour,
    ajouter_evenement,
    check_out,
    annuler_location,
    # enregistrer_paiement,  # ❌ SUPPRIMER
)
from .api import (
    api_annuler_location,
    api_ca_evolution,
    api_checkout_location,
    api_clients,
    api_locations,
    api_paiement_location,
    api_save_client,
    api_save_location,
    api_save_unite,
    api_stats,
    api_supprimer_unite,
    api_unites,
)

__all__ = [
    'dashboard',
    'liste_clients',
    'detail_client',
    'ajouter_client',
    'modifier_client',
    'liste_unites',
    'detail_unite',
    'ajouter_unite',
    'modifier_unite',
    'changer_statut_unite',
    'liste_locations',
    'detail_location',
    'ajouter_sejour',
    'ajouter_evenement',
    'check_out',
    'annuler_location',
    'api_annuler_location',
    'api_ca_evolution',
    'api_checkout_location',
    'api_clients',
    'api_locations',
    'api_paiement_location',
    'api_save_client',
    'api_save_location',
    'api_save_unite',
    'api_stats',
    'api_supprimer_unite',
    'api_unites',
]


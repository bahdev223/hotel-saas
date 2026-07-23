# apps/tresorerie/views/__init__.py
from .dashboard import dashboard_tresorier
from .caisses import liste_caisses, detail_caisse, ajouter_caisse, modifier_caisse, supprimer_caisse
from .mouvements import liste_mouvements
from .transferts import liste_transferts, transfert_caisse
from .cloture import cloturer_caisse
from .api import (
    api_ajouter_caisse,
    api_liste_caisses,
    api_detail_caisse,
    api_mouvement_caisse,
    api_historique_caisse,
    api_synthese_caisses,
    api_transfert_caisse,
)

__all__ = [
    'dashboard_tresorier',
    'liste_caisses',
    'detail_caisse',
    'ajouter_caisse',
    'modifier_caisse',
    'liste_mouvements',
    'liste_transferts',
    'transfert_caisse',
    'cloturer_caisse',
    'api_ajouter_caisse',
    'api_liste_caisses',
    'api_detail_caisse',
    'api_mouvement_caisse',
    'api_historique_caisse',
    'api_synthese_caisses',
    'api_transfert_caisse',
]

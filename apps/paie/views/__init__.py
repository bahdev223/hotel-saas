from .dashboard import dashboard
from .bulletins import liste_bulletins, detail_bulletin, generer_bulletins, valider_bulletin
from .rubriques import liste_rubriques, api_ajouter_rubrique, api_detail_rubrique, modifier_rubrique, supprimer_rubrique, toggle_rubrique
from .periodes import liste_periodes, creer_periode
from .avances import liste_avances, ajouter_avance, approuver_avance, payer_avance, rejeter_avance, api_detail_avance

__all__ = [
    'dashboard',
    'liste_bulletins', 'detail_bulletin', 'generer_bulletins', 'valider_bulletin',
    'liste_rubriques',
    'api_ajouter_rubrique', 'api_detail_rubrique', 'modifier_rubrique', 'supprimer_rubrique', 'toggle_rubrique',
    'liste_periodes', 'creer_periode',
    'liste_avances', 'ajouter_avance', 'approuver_avance', 'payer_avance', 'rejeter_avance', 'api_detail_avance',
]


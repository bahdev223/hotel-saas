from .dashboard import dashboard
from .employes import liste_employes, ajouter_employe, detail_employe, modifier_employe, supprimer_employe
from .departements import liste_departements, api_ajouter_departement, api_detail_departement, supprimer_departement
from .postes import liste_postes, api_ajouter_poste, api_detail_poste, modifier_poste, supprimer_poste, api_prochain_code_poste
from .api import api_ajouter_employe, api_prochain_matricule, api_detail_employe, api_modifier_employe, api_supprimer_compte_employe, api_desactiver_compte_employe, api_activer_compte_employe, api_supprimer_employe

__all__ = [
    'dashboard',
    'liste_employes', 'ajouter_employe', 'detail_employe', 'modifier_employe', 'supprimer_employe',
    'liste_departements', 'api_ajouter_departement', 'api_detail_departement', 'supprimer_departement',
    'liste_postes', 'api_ajouter_poste', 'api_detail_poste', 'modifier_poste', 'supprimer_poste', 'api_prochain_code_poste',
    'api_ajouter_employe', 'api_prochain_matricule', 'api_detail_employe', 'api_modifier_employe',
    'api_supprimer_compte_employe', 'api_desactiver_compte_employe', 'api_activer_compte_employe',
    'api_supprimer_employe',
]

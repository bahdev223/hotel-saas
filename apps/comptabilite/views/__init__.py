# apps/comptabilite/views/__init__.py
from .dashboard import dashboard
from .ecritures import ecritures_liste, ecriture_detail, ecriture_valider
from .comptes import liste_comptes, ajouter_compte, modifier_compte, detail_compte
from .bilan import bilan, compte_resultat, balance
from .grand_livre import grand_livre
from .flux_tresorerie import flux_tresorerie
from .api import api_ajouter_compte, api_ajouter_sous_compte, api_creer_ecriture_manuelle, api_liste_comptes, api_liste_journaux
from .journaux import journaux_liste, journal_detail, achats_liste, achat_detail
from .parametres import (
    exercices_liste, 
    cloturer_exercice, 
    rouvrir_exercice, 
    initialisation_soldes, 
    verifier_initialisation, 
    enregistrer_initialisation,
    initialisation_plan_comptable,
    api_initialiser_plan_comptable, 
    api_stats_plan_comptable,
    assistant_situation_initiale,
    api_etat_avancement,
    api_valider_situation,
)
from .exports import export_balance_pdf, export_balance_excel, export_bilan_pdf, export_resultat_pdf, export_ecritures_csv, export_ecritures_excel
from .amortissements import immobilisations_liste, immobilisation_ajouter, immobilisation_detail, generer_ecriture_amortissement, api_amortissements_mois
from .rapprochement import releves_liste, releve_detail, releve_importer, api_rapprocher_ligne, api_creer_ecart, api_mouvements_caisse

# 🔥 NOUVEAU : Opérations comptables
from .operations import (
    liste_operations,
    creer_achat,
    creer_vente,
    creer_depense,
    creer_recette,
    creer_depot_client,
    creer_paiement_fournisseur,
    creer_paiement_client,
    creer_remboursement_client,
    creer_depot_banque,
    creer_retrait_banque,
    detail_operation,
    lettrer_operation,
    api_calcul_tva,
)


__all__ = [
    # Dashboard
    'dashboard',
    
    # Écritures
    'ecritures_liste',
    'ecriture_detail',
    'ecriture_valider',
    
    # Comptes
    'liste_comptes',
    'ajouter_compte',
    'modifier_compte',
    'detail_compte',
    
    # États financiers
    'bilan',
    'compte_resultat',
    'balance',
    
    # API
    'api_ajouter_compte',
    'api_ajouter_sous_compte',
    'api_creer_ecriture_manuelle',
    'api_liste_comptes',
    'api_liste_journaux',
    
    # Journaux
    'journaux_liste',
    'journal_detail',
    'achats_liste',
    'achat_detail',
    
    # Paramètres
    'exercices_liste',
    'cloturer_exercice',
    'rouvrir_exercice',
    'initialisation_soldes',
    'verifier_initialisation',
    'enregistrer_initialisation',
    'initialisation_plan_comptable',
    'api_initialiser_plan_comptable',
    'api_stats_plan_comptable',
    'assistant_situation_initiale',
    'api_etat_avancement',
    'api_valider_situation',
    
    # Exports
    'export_balance_pdf',
    'export_balance_excel',
    'export_bilan_pdf',
    'export_resultat_pdf',
    'export_ecritures_csv',
    'export_ecritures_excel',
    
    # Amortissements
    'immobilisations_liste',
    'immobilisation_ajouter',
    'immobilisation_detail',
    'generer_ecriture_amortissement',
    'api_amortissements_mois',
    
    # Rapprochement
    'releves_liste',
    'releve_detail',
    'releve_importer',
    'api_rapprocher_ligne',
    'api_creer_ecart',
    'api_mouvements_caisse',
    
    # 🔥 Opérations comptables (NOUVEAU)
    'liste_operations',
    'creer_achat',
    'creer_vente',
    'creer_depense',
    'creer_recette',
    'creer_depot_client',
    'creer_paiement_fournisseur',
    'creer_paiement_client',
    'creer_remboursement_client',
    'creer_depot_banque',
    'creer_retrait_banque',
    'detail_operation',
    'lettrer_operation',
    'api_calcul_tva',
]


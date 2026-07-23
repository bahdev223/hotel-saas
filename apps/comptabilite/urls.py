# apps/comptabilite/urls.py
from django.urls import path
from . import views

app_name = 'comptabilite'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # ========== ÉCRITURES ==========
    path('ecritures/', views.ecritures_liste, name='ecritures_liste'),
    path('ecritures/<int:ecriture_id>/', views.ecriture_detail, name='ecriture_detail'),
    path('ecritures/<int:ecriture_id>/valider/', views.ecriture_valider, name='ecriture_valider'),
    
    # ========== COMPTES ==========
    path('comptes/', views.liste_comptes, name='comptes_liste'),
    path('comptes/ajouter/', views.ajouter_compte, name='ajouter_compte'),
    path('comptes/<int:compte_id>/', views.detail_compte, name='detail_compte'),
    path('comptes/<int:compte_id>/modifier/', views.modifier_compte, name='modifier_compte'),
    
    # ========== JOURNAUX ==========
    path('journaux/', views.journaux_liste, name='journaux_liste'),
    path('journaux/<int:journal_id>/', views.journal_detail, name='journal_detail'),
    
    # ========== ÉTATS FINANCIERS ==========
    path('bilan/', views.bilan, name='bilan'),
    path('compte-resultat/', views.compte_resultat, name='compte_resultat'),
    path('balance/', views.balance, name='balance'),
    path('grand-livre/', views.grand_livre, name='grand_livre'),
    path('grand-livre/<str:compte_code>/', views.grand_livre, name='grand_livre_compte'),
    path('flux-tresorerie/', views.flux_tresorerie, name='flux_tresorerie'),
    
    # ========== EXPORTS ==========
    path('export/balance/pdf/', views.export_balance_pdf, name='export_balance_pdf'),
    path('export/balance/excel/', views.export_balance_excel, name='export_balance_excel'),
    path('export/bilan/pdf/', views.export_bilan_pdf, name='export_bilan_pdf'),
    path('export/resultat/pdf/', views.export_resultat_pdf, name='export_resultat_pdf'),
    path('export/ecritures/csv/', views.export_ecritures_csv, name='export_ecritures_csv'),
    path('export/ecritures/excel/', views.export_ecritures_excel, name='export_ecritures_excel'),
    
    # ========== PARAMÈTRES ==========
    path('exercices/', views.exercices_liste, name='exercices_liste'),
    path('exercices/<int:exercice_id>/cloturer/', views.cloturer_exercice, name='cloturer_exercice'),
    path('exercices/<int:exercice_id>/rouvrir/', views.rouvrir_exercice, name='rouvrir_exercice'),
    
    # ========== INITIALISATION ==========
    path('initialisation/', views.initialisation_soldes, name='initialisation_soldes'),
    path('initialisation/verifier/', views.verifier_initialisation, name='verifier_initialisation'),
    path('initialisation/enregistrer/', views.enregistrer_initialisation, name='enregistrer_initialisation'),
    path('initialisation/plan-comptable/', views.initialisation_plan_comptable, name='initialisation_plan_comptable'),
    path('situation-initiale/', views.assistant_situation_initiale, name='situation_initiale'),
    path('situation-initiale/api/etat/', views.api_etat_avancement, name='api_etat_avancement'),
    path('situation-initiale/api/valider/', views.api_valider_situation, name='api_valider_situation'),
    
    # ========== ACHATS ==========
    path('achats/', views.achats_liste, name='achats_liste'),
    path('achats/<int:achat_id>/', views.achat_detail, name='achat_detail'),
    
    # ========== AMORTISSEMENTS ==========
    path('immobilisations/', views.immobilisations_liste, name='immobilisations_liste'),
    path('immobilisations/ajouter/', views.immobilisation_ajouter, name='immobilisation_ajouter'),
    path('immobilisations/<int:immobilisation_id>/', views.immobilisation_detail, name='immobilisation_detail'),
    path('amortissements/generer/<int:plan_id>/', views.generer_ecriture_amortissement, name='generer_ecriture_amortissement'),
    path('api/amortissements/mois/', views.api_amortissements_mois, name='api_amortissements_mois'),
    
    # ========== RAPPROCHEMENT BANCAIRE ==========
    path('rapprochement/', views.releves_liste, name='releves_liste'),
    path('rapprochement/<int:releve_id>/', views.releve_detail, name='releve_detail'),
    path('rapprochement/importer/', views.releve_importer, name='releve_importer'),
    path('api/rapprochement/ligne/', views.api_rapprocher_ligne, name='api_rapprocher_ligne'),
    path('api/rapprochement/ecart/', views.api_creer_ecart, name='api_creer_ecart'),
    path('api/rapprochement/mouvements/', views.api_mouvements_caisse, name='api_mouvements_caisse'),
    
    # ========== API GÉNÉRALES ==========
    path('api/comptes/ajouter/', views.api_ajouter_compte, name='api_ajouter_compte'),
    path('api/sous-comptes/ajouter/', views.api_ajouter_sous_compte, name='api_ajouter_sous_compte'),
    path('api/initialiser-plan-comptable/', views.api_initialiser_plan_comptable, name='api_initialiser_plan_comptable'),
    path('api/stats-plan-comptable/', views.api_stats_plan_comptable, name='api_stats_plan_comptable'),
    path('api/ecritures/manuelle/', views.api_creer_ecriture_manuelle, name='api_creer_ecriture_manuelle'),
    path('api/comptes/liste/', views.api_liste_comptes, name='api_liste_comptes'),
    path('api/journaux/liste/', views.api_liste_journaux, name='api_liste_journaux'),
    
    # 🔥 NOUVEAU : OPÉRATIONS COMPTABLES 🔥
    path('operations/', views.liste_operations, name='operations'),
    path('operations/achat/', views.creer_achat, name='creer_achat'),
    path('operations/vente/', views.creer_vente, name='creer_vente'),
    path('operations/depense/', views.creer_depense, name='creer_depense'),
    path('operations/recette/', views.creer_recette, name='creer_recette'),
    path('operations/depot-client/', views.creer_depot_client, name='creer_depot_client'),
    path('operations/paiement-fournisseur/', views.creer_paiement_fournisseur, name='creer_paiement_fournisseur'),
    path('operations/paiement-client/', views.creer_paiement_client, name='creer_paiement_client'),
    path('operations/remboursement-client/', views.creer_remboursement_client, name='creer_remboursement_client'),
    path('operations/depot-banque/', views.creer_depot_banque, name='creer_depot_banque'),
    path('operations/retrait-banque/', views.creer_retrait_banque, name='creer_retrait_banque'),
    path('operations/<str:operation_id>/', views.detail_operation, name='detail_operation'),
    path('operations/<str:operation_id>/lettrer/', views.lettrer_operation, name='lettrer_operation'),
    path('api/calcul-tva/', views.api_calcul_tva, name='api_calcul_tva'),
]


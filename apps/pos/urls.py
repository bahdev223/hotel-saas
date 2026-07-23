# apps/pos/urls.py
from django.urls import path
from . import views

app_name = 'pos'

urlpatterns = [
    # ========== EMPLOYÉ DASHBOARD ==========
    path('mon-espace/', views.employe_dashboard, name='employe_dashboard'),
    path('api/mon-espace/', views.api_mon_espace, name='api_mon_espace'),

    # ========== POINTS DE VENTE ==========
    path('', views.liste_points_vente, name='liste_points_vente'),
    path('ajouter/', views.ajouter_point_vente, name='ajouter_point_vente'),
    path('<int:point_id>/', views.detail_point_vente, name='detail_point_vente'),
    path('<int:point_id>/modifier/', views.modifier_point_vente, name='modifier_point_vente'),
    path('<int:point_id>/supprimer/', views.supprimer_point_vente, name='supprimer_point_vente'),
    path('<int:point_id>/changer-responsable/', views.changer_responsable, name='changer_responsable'),
    path('<int:point_id>/changer-entrepot/', views.changer_entrepot, name='changer_entrepot'),
    path('api/point-vente/<int:point_id>/entrepot/ajouter/', views.api_ajouter_entrepot_pv, name='api_ajouter_entrepot_pv'),
    path('api/point-vente/<int:point_id>/entrepot/retirer/', views.api_retirer_entrepot_pv, name='api_retirer_entrepot_pv'),
    path('api/caisses/ajouter/', views.api_ajouter_caisse, name='api_ajouter_caisse'),
    path('api/point-vente/ajouter/', views.api_ajouter_point_vente, name='api_ajouter_point_vente'),
    path('api/point-vente/dashboard/', views.api_point_vente_dashboard, name='api_point_vente_dashboard'),
    
    # ========== VENTES (historique) ==========
    path('ventes/', views.liste_ventes, name='liste_ventes'),
    
    # ========== SESSIONS ==========
    path('sessions/', views.sessions_liste, name='sessions_liste'),
    path('sessions/<int:session_id>/', views.session_detail, name='session_detail'),
    path('api/sessions/ouvrir/', views.api_ouverture_session, name='api_ouverture_session'),
    path('api/sessions/fermer/', views.api_fermeture_session, name='api_fermeture_session'),
    path('api/sessions/cloturer-rouvrir/', views.api_cloturer_et_rouvrir, name='api_cloturer_et_rouvrir'),
    path('api/sessions/active/<int:point_vente_id>/', views.api_session_active, name='api_session_active'),
    path('api/sessions/verifier-etat/<int:point_vente_id>/', views.api_verifier_etat_pos, name='api_verifier_etat_pos'),
    path('api/sessions/caissiers/<int:point_vente_id>/', views.api_caissiers_disponibles, name='api_caissiers_disponibles'),
    path('sessions/<int:session_id>/export-csv/', views.session_export_csv, name='session_export_csv'),
    
    # ========== COMMANDES (NOUVEAU) ==========
    path('commandes/', views.dashboard_commandes, name='dashboard_commandes'),
    path('commandes/cuisine/', views.cuisine_dashboard, name='cuisine_dashboard'),
    path('api/commandes/creer/', views.api_creer_commande, name='api_creer_commande'),
    path('api/commandes/liste/', views.liste_commandes_api, name='liste_commandes_api'),
    path('api/commandes/<int:commande_id>/', views.detail_commande, name='detail_commande'),
    path('api/commandes/<int:commande_id>/changer-statut/', views.changer_statut_commande, name='changer_statut_commande'),
    path('api/commandes/<int:commande_id>/paiement/', views.api_payer_commande, name='api_payer_commande'),
    path('api/commandes/<int:commande_id>/annuler/', views.api_raf_annuler_commande, name='api_raf_annuler_commande'),
    path('api/commandes/payees/', views.api_raf_liste_commandes_payees, name='api_raf_liste_commandes_payees'),
    path('api/ventes/<int:vente_id>/recu/', views.api_vente_recu, name='api_vente_recu'),
    
    # ========== POS INTERFACE ==========
    path('raf/', views.pos_raf, name='pos_raf'),
    path('raf/dashboard/', views.raf_dashboard, name='raf_dashboard'),
    path('raf/collecte/', views.raf_collecte, name='raf_collecte'),
    path('raf/transferts/', views.raf_transferts, name='raf_transferts'),
    path('api/raf/liste-sessions/', views.raf_liste_collecte_api, name='raf_liste_collecte_api'),
    path('api/raf/ouvrir-depot/', views.raf_ouvrir_depot_api, name='raf_ouvrir_depot_api'),
    path('api/raf/declarer-solde-initial/', views.raf_declarer_solde_initial_api, name='raf_declarer_solde_initial_api'),
    path('api/raf/collecter/', views.raf_collecter_api, name='raf_collecter_api'),
    path('api/raf/dashboard-data/', views.raf_dashboard_data_api, name='raf_dashboard_data_api'),
    path('caisse/<slug:slug>/', views.pos_by_slug, name='pos_by_slug'),
    path('api/ventes/', views.api_liste_ventes, name='api_liste_ventes'),
    path('api/produits/', views.api_produits, name='api_produits'),
    path('api/clients/recherche/', views.api_recherche_clients, name='api_recherche_clients'),
    path('api/clients/creer/', views.api_creer_client, name='api_creer_client'),
    path('api/paiement-clients/processer/', views.api_paiement_clients_processer, name='api_paiement_clients_processer'),
    path('mon-espace/paiement-clients/', views.employe_paiement_clients, name='employe_paiement_clients'),
    
    # ========== PLANNING SESSIONS ==========
    path('planning/', views.planning_view, name='planning'),
    path('api/planning/liste/', views.api_planning_liste, name='api_planning_liste'),
    path('api/planning/creer/', views.api_planning_creer, name='api_planning_creer'),
    path('api/planning/creer-masse/', views.api_planning_creer_masse, name='api_planning_creer_masse'),
    path('api/planning/supprimer/', views.api_planning_supprimer, name='api_planning_supprimer'),
    path('api/planning/employes/', views.api_planning_employes, name='api_planning_employes'),
    path('api/planning/set-horaire/', views.api_set_horaire, name='api_set_horaire'),
]



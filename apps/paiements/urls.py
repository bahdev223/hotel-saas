# apps/paiements/urls.py
from django.urls import path
from . import views

app_name = 'paiements'

urlpatterns = [
    # Liste des paiements
    path('', views.liste_paiements, name='liste_paiements'),

    # Détail d'un paiement
    path('<int:paiement_id>/', views.detail_paiement, name='detail_paiement'),

    # Annuler un paiement
    path('<int:paiement_id>/annuler/', views.annuler_paiement, name='annuler_paiement'),

    # API Stats
    path('api/statistiques/', views.api_stats_paiements, name='api_stats_paiements'),

    # ===== PAYMENT ENGINE API =====
    path('api/processer/', views.api_process_paiement, name='api_process_paiement'),
    path('api/factures-impayees/', views.api_factures_impayees, name='api_factures_impayees'),
    path('api/commandes-impayees/', views.api_commandes_impayees, name='api_commandes_impayees'),
    path('api/caisses/', views.api_caisses_disponibles, name='api_caisses_disponibles'),
    path('api/clients/recherche/', views.api_recherche_clients, name='api_recherche_clients'),
    path('api/clients/<str:client_id>/solde/', views.api_solde_client, name='api_solde_client'),
    path('api/clients/<str:client_id>/dettes/', views.api_dettes_client, name='api_dettes_client'),

    # ===== RECU =====
    path('<int:paiement_id>/recu/', views.recu_paiement, name='recu_paiement'),
]

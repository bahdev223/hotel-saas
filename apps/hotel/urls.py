# apps/hotel/urls.py
from django.urls import path
from . import views

app_name = 'hotel'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),

    # ========== API DASHBOARD ==========
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/ca-evolution/', views.api_ca_evolution, name='api_ca_evolution'),
    path('api/clients/', views.api_clients, name='api_clients'),
    path('api/clients/save/', views.api_save_client, name='api_save_client'),
    path('api/unites/', views.api_unites, name='api_unites'),
    path('api/unites/save/', views.api_save_unite, name='api_save_unite'),
    path('api/unites/<str:unite_id>/supprimer/', views.api_supprimer_unite, name='api_supprimer_unite'),
    path('api/locations/', views.api_locations, name='api_locations'),
    path('api/locations/save/', views.api_save_location, name='api_save_location'),
    path('api/locations/<str:location_id>/paiement/', views.api_paiement_location, name='api_paiement_location'),
    path('api/locations/<str:location_id>/checkout/', views.api_checkout_location, name='api_checkout_location'),
    path('api/locations/<str:location_id>/annuler/', views.api_annuler_location, name='api_annuler_location'),

    # ========== CLIENTS ==========
    path('clients/', views.liste_clients, name='liste_clients'),
    path('clients/ajouter/', views.ajouter_client, name='ajouter_client'),
    path('clients/<str:client_id>/', views.detail_client, name='detail_client'),
    path('clients/<str:client_id>/modifier/', views.modifier_client, name='modifier_client'),

    # ========== UNITÉS (chambres, salles, espaces) ==========
    path('unites/', views.liste_unites, name='liste_unites'),
    path('unites/ajouter/', views.ajouter_unite, name='ajouter_unite'),
    path('unites/<str:unite_id>/', views.detail_unite, name='detail_unite'),
    path('unites/<str:unite_id>/modifier/', views.modifier_unite, name='modifier_unite'),
    path('unites/<str:unite_id>/changer-statut/', views.changer_statut_unite, name='changer_statut_unite'),
    path('chambres/', views.liste_unites, name='liste_chambres'),
    path('salles/', views.liste_unites, name='liste_salles'),

    # ========== LOCATIONS (séjours et événements) ==========
    path('locations/', views.liste_locations, name='liste_locations'),
    path('locations/<str:location_id>/', views.detail_location, name='detail_location'),
    path('locations/ajouter/sejour/', views.ajouter_sejour, name='ajouter_sejour'),
    path('locations/ajouter/evenement/', views.ajouter_evenement, name='ajouter_evenement'),
    path('locations/<str:location_id>/check-out/', views.check_out, name='check_out'),
    path('locations/<str:location_id>/annuler/', views.annuler_location, name='annuler_location'),
    # ❌ SUPPRIMER cette ligne
    # path('locations/<str:location_id>/paiement/', views.enregistrer_paiement, name='enregistrer_paiement'),
    
    # Aliases
    path('sejours/', views.liste_locations, name='liste_sejours'),
    path('reservations/chambres/', views.liste_locations, name='liste_reservations_chambres'),
]



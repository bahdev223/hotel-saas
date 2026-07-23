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
    path('api/tarifs/', views.api_tarifs, name='api_tarifs'),
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
    
    # ========== TARIFS ==========
    path('tarifs/', views.grille_tarifs, name='grille_tarifs'),
    path('tarifs/ajouter/', views.ajouter_tarif, name='ajouter_tarif'),
    path('tarifs/<int:tarif_id>/modifier/', views.modifier_tarif, name='modifier_tarif'),
    path('tarifs/<int:tarif_id>/desactiver/', views.desactiver_tarif, name='desactiver_tarif'),
    path('tarifs/plans/', views.liste_plans, name='liste_plans'),
    path('tarifs/types/', views.liste_types_tarif, name='liste_types_tarif'),
    path('tarifs/creneaux/', views.liste_creneaux, name='liste_creneaux'),

    # ========== TYPES DE CHAMBRES ==========

    # ========== RÉSERVATIONS ==========
    path('reservations/', views.liste_reservations, name='liste_reservations'),
    path('reservations/ajouter/', views.ajouter_reservation, name='ajouter_reservation'),
    path('reservations/<str:reservation_id>/', views.detail_reservation, name='detail_reservation'),
    path('reservations/<str:reservation_id>/annuler/', views.annuler_reservation, name='annuler_reservation'),

    # ========== SÉJOURS ==========
    path('sejours/', views.liste_sejours, name='liste_sejours'),
    path('sejours/<str:sejour_id>/', views.detail_sejour, name='detail_sejour'),
    path('sejours/<str:sejour_id>/check-out/', views.check_out, name='check_out'),
    path('sejours/<str:sejour_id>/cloturer/', views.cloturer_sejour, name='cloturer_sejour'),
    path('check-in/', views.check_in, name='check_in'),

    # Aliases
    path('reservations/chambres/', views.liste_reservations, name='liste_reservations_chambres'),
]



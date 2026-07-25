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
    path('api/unites/', views.api_unites, name='api_unites'),
    path('api/unites/save/', views.api_save_unite, name='api_save_unite'),
    path('api/unites/<str:unite_id>/supprimer/', views.api_supprimer_unite, name='api_supprimer_unite'),
    path('api/tarifs/', views.api_tarifs, name='api_tarifs'),
    path('api/tarifs/save/', views.api_save_tarif, name='api_save_tarif'),
    path('api/tarifs/<int:tarif_id>/supprimer/', views.api_supprimer_tarif, name='api_supprimer_tarif'),

    # ========== UNITÉS (chambres, salles, espaces) ==========
    path('unites/', views.liste_unites, name='liste_unites'),
    path('unites/ajouter/', views.ajouter_unite, name='ajouter_unite'),
    path('unites/<str:unite_id>/', views.detail_unite, name='detail_unite'),
    path('unites/<str:unite_id>/modifier/', views.modifier_unite, name='modifier_unite'),
    path('unites/<str:unite_id>/changer-statut/', views.changer_statut_unite, name='changer_statut_unite'),
    path('chambres/', views.liste_unites, name='liste_chambres'),
    path('salles/', views.liste_unites, name='liste_salles'),

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

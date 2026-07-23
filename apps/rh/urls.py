from django.urls import path
from . import views

app_name = 'rh'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    # Employés
    path('employes/', views.liste_employes, name='liste_employes'),
    path('employes/ajouter/', views.ajouter_employe, name='ajouter_employe'),
    path('employes/<str:matricule>/', views.detail_employe, name='detail_employe'),
    path('employes/<str:matricule>/modifier/', views.modifier_employe, name='modifier_employe'),
    path('employes/<str:matricule>/supprimer/', views.supprimer_employe, name='supprimer_employe'),
    path('employes/<str:matricule>/api/', views.api_detail_employe, name='api_detail_employe'),
    path('employes/<str:matricule>/api/modifier/', views.api_modifier_employe, name='api_modifier_employe'),
    path('employes/api/ajouter/', views.api_ajouter_employe, name='api_ajouter_employe'),
    path('employes/api/prochain-matricule/', views.api_prochain_matricule, name='api_prochain_matricule'),
    path('employes/<str:matricule>/api/supprimer-compte/', views.api_supprimer_compte_employe, name='api_supprimer_compte'),
    path('employes/<str:matricule>/api/desactiver-compte/', views.api_desactiver_compte_employe, name='api_desactiver_compte'),
    path('employes/<str:matricule>/api/activer-compte/', views.api_activer_compte_employe, name='api_activer_compte'),
    path('employes/<str:matricule>/api/supprimer/', views.api_supprimer_employe, name='api_supprimer_employe'),

    # Départements
    path('departements/', views.liste_departements, name='liste_departements'),
    path('departements/api/ajouter/', views.api_ajouter_departement, name='api_ajouter_departement'),
    path('departements/<int:dept_id>/api/', views.api_detail_departement, name='api_detail_departement'),
    path('departements/<int:dept_id>/supprimer/', views.supprimer_departement, name='supprimer_departement'),

    # Postes
    path('postes/', views.liste_postes, name='liste_postes'),
    path('postes/api/ajouter/', views.api_ajouter_poste, name='api_ajouter_poste'),
    path('postes/api/prochain-code/', views.api_prochain_code_poste, name='api_prochain_code_poste'),
    path('postes/<int:poste_id>/api/', views.api_detail_poste, name='api_detail_poste'),
    path('postes/<int:poste_id>/modifier/', views.modifier_poste, name='modifier_poste'),
    path('postes/<int:poste_id>/supprimer/', views.supprimer_poste, name='supprimer_poste'),


]


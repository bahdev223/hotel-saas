# apps/authentication/urls.py
from django.urls import path
from . import views

app_name = 'authentication'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('creer/', views.creer_utilisateur, name='creer_utilisateur'),
    path('profil/', views.mon_profil, name='mon_profil'),
    path('accueil/', views.employe_accueil, name='employe_accueil'),
    path('changer-mdp/', views.changer_mot_de_passe, name='changer_mot_de_passe'),
    path('mdp-oublie/', views.mot_de_passe_oublie, name='mot_de_passe_oublie'),
    path('reset/<str:token>/', views.reset_mot_de_passe, name='reset_mot_de_passe'),
    path('reinitialiser/<int:user_id>/', views.reinitialiser_mot_de_passe, name='reinitialiser_mot_de_passe'),
]

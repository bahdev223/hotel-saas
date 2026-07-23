# apps/tresorerie/urls.py
from django.urls import path
from . import views

app_name = 'tresorerie'

urlpatterns = [
    
    path('', views.dashboard_tresorier, name='dashboard_tresorier'),
    path('liste/', views.liste_caisses, name='liste_caisses'),
    path('ajouter/', views.ajouter_caisse, name='ajouter_caisse'),
    path('<int:caisse_id>/modifier/', views.modifier_caisse, name='modifier_caisse'),
    path('<int:caisse_id>/supprimer/', views.supprimer_caisse, name='supprimer_caisse'),
    path('<int:caisse_id>/', views.detail_caisse, name='detail_caisse'),
    path('<int:caisse_id>/cloturer/', views.cloturer_caisse, name='cloturer_caisse'),
    path('mouvements/', views.liste_mouvements, name='liste_mouvements'),
    path('transferts/', views.transfert_caisse, name='transfert_caisse'),
    path('transferts/liste/', views.liste_transferts, name='liste_transferts'),

    # API
    path('api/caisses/', views.api_liste_caisses, name='api_liste_caisses'),
    path('api/caisses/ajouter/', views.api_ajouter_caisse, name='api_ajouter_caisse'),
    path('api/caisses/<int:caisse_id>/', views.api_detail_caisse, name='api_detail_caisse'),
    path('api/caisses/<int:caisse_id>/historique/', views.api_historique_caisse, name='api_historique_caisse'),
    path('api/mouvement/', views.api_mouvement_caisse, name='api_mouvement_caisse'),
    path('api/synthese/', views.api_synthese_caisses, name='api_synthese_caisses'),
    path('api/transfert/', views.api_transfert_caisse, name='api_transfert_caisse'),
]
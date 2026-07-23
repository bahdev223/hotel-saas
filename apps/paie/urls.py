from django.urls import path
from . import views

app_name = 'paie'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('bulletins/', views.liste_bulletins, name='liste_bulletins'),
    path('bulletins/<str:bulletin_id>/', views.detail_bulletin, name='detail_bulletin'),
    path('bulletins/<str:bulletin_id>/valider/', views.valider_bulletin, name='valider_bulletin'),
    path('periodes/<int:periode_id>/generer/', views.generer_bulletins, name='generer_bulletins'),
   
    path('periodes/', views.liste_periodes, name='liste_periodes'),
    path('periodes/creer/', views.creer_periode, name='creer_periode'),
    

    # Rubriques
    path('rubriques/', views.liste_rubriques, name='liste_rubriques'),
    path('rubriques/api/ajouter/', views.api_ajouter_rubrique, name='api_ajouter_rubrique'),
    path('rubriques/<int:rubrique_id>/api/', views.api_detail_rubrique, name='api_detail_rubrique'),
    path('rubriques/<int:rubrique_id>/modifier/', views.modifier_rubrique, name='modifier_rubrique'),
    path('rubriques/<int:rubrique_id>/supprimer/', views.supprimer_rubrique, name='supprimer_rubrique'),
    path('rubriques/<int:rubrique_id>/toggle/', views.toggle_rubrique, name='toggle_rubrique'),
    
    
    # Avances sur salaire
    path('avances/', views.liste_avances, name='liste_avances'),
    path('avances/ajouter/', views.ajouter_avance, name='ajouter_avance'),
    path('avances/<str:avance_id>/approuver/', views.approuver_avance, name='approuver_avance'),
    path('avances/<str:avance_id>/payer/', views.payer_avance, name='payer_avance'),
    path('avances/<str:avance_id>/rejeter/', views.rejeter_avance, name='rejeter_avance'),
    path('avances/<str:avance_id>/api/', views.api_detail_avance, name='api_detail_avance'),
    
    
]

from django.urls import path
from . import views

app_name = 'fournisseurs'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),

    path('ajouter/', views.ajouter, name='ajouter'),
    path('<str:fournisseur_id>/', views.detail, name='detail'),
    path('<str:fournisseur_id>/modifier/', views.modifier, name='modifier'),
    path('<str:fournisseur_id>/supprimer/', views.supprimer, name='supprimer'),
]

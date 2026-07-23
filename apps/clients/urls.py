# apps/clients/urls.py
from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'clients'

urlpatterns = [
    path('', RedirectView.as_view(pattern_name='clients:liste', permanent=True)),
    path('liste/', views.dashboard, name='liste'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('ajouter/', views.ajouter_client, name='ajouter'),
    path('<str:client_id>/', views.detail_client, name='detail'),
    path('<str:client_id>/modifier/', views.modifier_client, name='modifier'),
    path('<str:client_id>/supprimer/', views.supprimer_client, name='supprimer'),
    path('<str:client_id>/statut/', views.changer_statut, name='changer_statut'),
]


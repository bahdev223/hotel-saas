from django.urls import path
from . import views

urlpatterns = [
    path('liste/', views.api_liste_clients, name='api_liste_clients'),
    path('<str:client_id>/detail/', views.api_detail_client, name='api_detail_client'),
]

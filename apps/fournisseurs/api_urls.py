from django.urls import path
from . import views

urlpatterns = [
    path('liste/', views.api_liste, name='api_liste'),
    path('<str:fournisseur_id>/detail/', views.api_detail, name='api_detail'),
    path('<str:fournisseur_id>/releve/', views.api_releve, name='api_releve'),
]

# apps/facturation/urls.py
from django.urls import path
from . import views

app_name = 'facturation'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Pages HTML
    path('liste/', views.liste_factures, name='liste'),
    path('creer/', views.creer_facture, name='creer'),
    path('<str:facture_id>/', views.detail_facture, name='detail'),
    path('<str:facture_id>/modifier/', views.modifier_facture, name='modifier'),
    path('<str:facture_id>/annuler/', views.annuler_facture, name='annuler'),
    path('<str:facture_id>/pdf/', views.export_pdf, name='pdf'),
    
    # Paiements
    path('<str:facture_id>/paiement/', views.ajouter_paiement, name='ajouter_paiement'),
    
    # Statistiques
    path('statistiques/', views.statistiques, name='statistiques'),
    
    # ========== API ==========
    path('api/factures/', views.api_factures, name='api_factures'),
    path('api/stats/', views.api_stats, name='api_stats'),
    path('api/factures/<str:facture_id>/paiement/', views.api_paiement, name='api_paiement'),
    
    # API Lignes
    path('api/factures/<str:facture_id>/lignes/', views.api_lignes, name='api_lignes'),
    path('api/factures/<str:facture_id>/lignes/ajouter/', views.api_ajouter_ligne, name='api_ajouter_ligne'),
    path('api/lignes/<str:ligne_id>/detail/', views.api_detail_ligne, name='api_detail_ligne'),
    path('api/lignes/<str:ligne_id>/modifier/', views.api_modifier_ligne, name='api_modifier_ligne'),
    path('api/lignes/<str:ligne_id>/supprimer/', views.api_supprimer_ligne, name='api_supprimer_ligne'),
]

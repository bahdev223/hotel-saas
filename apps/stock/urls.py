# apps/stock/urls.py
from django.urls import path
from . import views

app_name = 'stock'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Produits
    path('produits/', views.liste_produits, name='liste_produits'),
    path('produits/ajouter/', views.ajouter_produit, name='ajouter_produit'),
    path('produits/<int:produit_id>/', views.detail_produit, name='detail_produit'),
    path('produits/<int:produit_id>/modifier/', views.modifier_produit, name='modifier_produit'),
    path('produits/<int:produit_id>/supprimer/', views.supprimer_produit, name='supprimer_produit'),
    
    # Entrées stock 🔥 NOUVEAU
    path('entrees/', views.liste_entrees, name='liste_entrees'),
    path('api/entrees/', views.api_liste_entrees, name='api_liste_entrees'),
    path('api/entrees/ajouter/', views.api_ajouter_entree, name='api_ajouter_entree'),
    
    # Mouvements
    path('mouvements/', views.liste_mouvements, name='liste_mouvements'),
    path('mouvements/entree/', views.entree_stock, name='entree_stock'),
    path('mouvements/sortie/', views.sortie_stock, name='sortie_stock'),

    # Pertes
    path('pertes/', views.liste_pertes, name='liste_pertes'),
    path('api/pertes/declarer/', views.api_declarer_perte, name='api_declarer_perte'),
    
    # Transferts
    path('transferts/', views.liste_transferts, name='liste_transferts'),
    path('transferts/nouveau/', views.transfert_produits, name='transfert_produits'),
    
    # Entrepôts
    path('entrepots/', views.liste_entrepots, name='liste_entrepots'),
    path('entrepots/ajouter/', views.ajouter_entrepot, name='ajouter_entrepot'),
    path('entrepots/<int:entrepot_id>/', views.detail_entrepot, name='detail_entrepot'),
    path('entrepots/<int:entrepot_id>/modifier/', views.modifier_entrepot, name='modifier_entrepot'),
    
    # Fournisseurs
    path('fournisseurs/', views.liste_fournisseurs, name='liste_fournisseurs'),
    path('fournisseurs/<str:fournisseur_id>/', views.detail_fournisseur, name='detail_fournisseur'),
    
    # Inventaires
    path('inventaires/', views.liste_inventaires, name='liste_inventaires'),
    path('inventaires/creer/', views.creer_inventaire, name='creer_inventaire'),
    path('inventaires/<int:inventaire_id>/', views.detail_inventaire, name='detail_inventaire'),
    path('inventaires/<int:inventaire_id>/supprimer/', views.supprimer_inventaire, name='supprimer_inventaire'),
    
    # APIs
    path('api/produits/ajouter/', views.api_ajouter_produit, name='api_ajouter_produit'),
    path('api/produits/<int:produit_id>/infos/', views.api_produit_infos, name='api_produit_infos'),
    path('api/produits/<int:produit_id>/modifier/', views.api_modifier_produit, name='api_modifier_produit'),
    path('api/produits/<int:produit_id>/stock/', views.api_produit_stock, name='api_produit_stock'),
    path('api/produits/<int:produit_id>/stock-converti/', views.api_produit_stock_converti, name='api_produit_stock_converti'),
    path('api/produits/<int:produit_id>/modifier-prix/', views.modifier_prix_produit, name='modifier_prix_produit'),
    path('api/produits/<int:produit_id>/image/', views.api_modifier_image_produit, name='api_modifier_image_produit'),
    path('api/produits/<int:produit_id>/image/supprimer/', views.api_supprimer_image_produit, name='api_supprimer_image_produit'),
    path('api/produits/<int:produit_id>/supprimer/', views.api_supprimer_produit, name='api_supprimer_produit'),
    path('api/recherche/code-barre/', views.api_recherche_code_barre, name='api_recherche_code_barre'),
    path('api/stock/entrepot/<int:entrepot_id>/produit/<int:produit_id>/', views.api_stock_by_entrepot_produit, name='api_stock_by_entrepot_produit'),
    path('api/entrepots/ajouter/', views.api_ajouter_entrepot, name='api_ajouter_entrepot'),
    
    # APIs Fournisseurs (legacy)
    path('api/fournisseurs/liste/', views.api_liste_fournisseurs, name='api_liste_fournisseurs'),
    path('api/fournisseurs/<str:fournisseur_id>/', views.api_detail_fournisseur, name='api_detail_fournisseur'),
    
    # APIs Transferts
    path('api/transferts/entrepot/', views.api_transfert_entrepot, name='api_transfert_entrepot'),
    path('api/transferts/bar/', views.api_transfert_bar, name='api_transfert_bar'),
    path('api/transferts/restaurant/', views.api_transfert_restaurant, name='api_transfert_restaurant'),
    
    # APIs Inventaire
    path('api/inventaire/lignes/<int:ligne_id>/', views.api_mettre_a_jour_ligne, name='api_mettre_a_jour_ligne'),
    path('api/inventaires/<int:inventaire_id>/lignes/', views.api_lignes_inventaire, name='api_lignes_inventaire'),
    path('api/inventaires/<int:inventaire_id>/valider/', views.api_valider_inventaire, name='api_valider_inventaire'),
    
    # Achats / Approvisionnements
    path('achats/', views.liste_achats, name='liste_achats'),
    path('api/achats/liste/', views.api_liste_achats, name='api_liste_achats'),
    path('api/achats/creer/', views.api_creer_achat, name='api_creer_achat'),

    # SPA APIs
    path('api/produits/liste/', views.api_liste_produits, name='api_liste_produits'),
    path('api/mouvements/liste/', views.api_liste_mouvements, name='api_liste_mouvements'),
    path('api/mouvements/motifs/', views.api_liste_motifs, name='api_liste_motifs'),
    path('api/sortie/ajouter/', views.api_ajouter_sortie, name='api_ajouter_sortie'),
    path('api/transferts/liste/', views.api_liste_transferts, name='api_liste_transferts'),
    path('api/transferts/effectuer/', views.api_effectuer_transfert, name='api_effectuer_transfert'),
    path('api/transferts/<int:mouvement_id>/annuler/', views.api_annuler_transfert, name='api_annuler_transfert'),
    path('api/entrepots/liste/', views.api_liste_entrepots, name='api_liste_entrepots'),
    path('api/entrepots/<int:entrepot_id>/stocks/', views.api_detail_entrepot_stocks, name='api_detail_entrepot_stocks'),
    path('api/entrepots/<int:entrepot_id>/produit/<int:produit_id>/supprimer/', views.api_supprimer_stock_entrepot, name='api_supprimer_stock_entrepot'),
    path('api/domaines/liste/', views.api_liste_domaines, name='api_liste_domaines'),
    path('api/categories/liste/', views.api_liste_categories, name='api_liste_categories'),
    path('api/notifications/', views.api_notifications_stock, name='api_notifications_stock'),
]

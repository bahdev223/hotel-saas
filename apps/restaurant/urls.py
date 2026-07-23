# apps/restaurant/urls.py
from django.urls import path
from . import views
from .views import menus

app_name = 'restaurant'

urlpatterns = [
    # Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # ========== FILE D'ATTENTE ==========
    path('file-attente/', views.file_attente, name='file_attente'),
    
    # ========== PRODUITS STOCK ==========
    path('produits/', views.produits_stock, name='produits_stock'),
    path('produits/ajouter/', views.ajouter_produit, name='ajouter_produit'),
    path('produits/<str:produit_id>/modifier/', views.modifier_produit, name='modifier_produit'),
    path('produits/<str:produit_id>/supprimer/', views.supprimer_produit, name='supprimer_produit'),
    path('produits/<str:produit_id>/entree/', views.entree_stock, name='entree_stock'),
    path('produits/<str:produit_id>/mouvements/', views.mouvement_stock, name='mouvement_stock'),
    path('api/produits/ajouter/', views.api_ajouter_produit, name='api_ajouter_produit'),
    path('api/produits/stock/', views.api_liste_produits_stock, name='api_liste_produits_stock'),
    path('api/produits/<str:produit_id>/infos/', views.api_produit_infos, name='api_produit_infos'),
    path('api/produits/<str:produit_id>/modifier/', views.api_modifier_produit, name='api_modifier_produit'),
    path('api/produits/<str:produit_id>/entree/', views.api_entree_stock, name='api_entree_stock'),
    path('api/produits/<str:produit_id>/supprimer/', views.api_supprimer_produit, name='api_supprimer_produit'),
    
    # ========== RECETTES ==========
    path('recettes/', views.recettes_liste, name='recettes'),
    path('recettes/ajouter/', views.recette_ajouter, name='recette_ajouter'),
    path('recettes/<str:recette_id>/', views.recette_detail, name='recette_detail'),
    path('recettes/<str:recette_id>/modifier/', views.recette_modifier, name='recette_modifier'),
    path('recettes/<str:recette_id>/supprimer/', views.recette_supprimer, name='recette_supprimer'),
    path('recettes/<str:recette_id>/dupliquer/', views.recette_dupliquer, name='recette_dupliquer'),
    path('recettes/<str:recette_id>/cout/', views.calcul_cout, name='calcul_cout'),
    
    # ========== MENUS ==========
    path('menus/', menus.menus_liste, name='menus_liste'),
    path('menus/<str:menu_id>/composer/', menus.menu_composer, name='menu_composer'),
    
    # ========== API MENUS ==========
    path('api/menus/', menus.api_menus_pos, name='api_menus_pos'),
    path('api/menus/<str:menu_id>/', menus.api_menu_detail, name='api_menu_detail'),
    path('api/menus/<str:menu_id>/lignes/', menus.api_menu_lignes, name='api_menu_lignes'),
    path('api/menus/composition/save/', views.api_save_menu_composition, name='api_save_menu_composition'),
    path('api/menu/ajouter/', menus.api_menu_ajouter, name='api_menu_ajouter'),
    path('api/menu/<str:menu_id>/get/', menus.api_menu_get, name='api_menu_get'),
    path('api/menu/<str:menu_id>/modifier/', menus.api_menu_modifier, name='api_menu_modifier'),
    path('api/menu/<str:menu_id>/recettes/', menus.api_menu_recettes, name='api_menu_recettes'),
    path('api/menu/<str:menu_id>/ajouter-recette/', menus.api_menu_ajouter_recette, name='api_menu_ajouter_recette'),
    path('api/menu/ligne/<str:ligne_id>/supprimer/', menus.api_menu_supprimer_ligne, name='api_menu_supprimer_ligne'),
    path('api/menu/<str:menu_id>/supprimer/', menus.api_menu_supprimer, name='api_menu_supprimer'),
    path('api/menu/<str:menu_id>/calculer-prix/', menus.api_menu_calculer_prix, name='api_menu_calculer_prix'),
    
    # ========== PRODUCTION ==========
    path('production/', views.production_dashboard, name='production_dashboard'),
    path('production/liste/', views.production_liste, name='production_liste'),
    path('production/<int:production_id>/', views.production_detail, name='production_detail'),
    
    # ========== API PRODUCTION ==========
    path('api/produire/', views.api_produire, name='api_produire'),
    path('api/production/<int:production_id>/annuler/', views.api_annuler_production, name='api_annuler_production'),
    path('api/production/historique/', views.api_historique_production, name='api_historique_production'),
    path('api/production/<int:production_id>/', views.api_production_detail, name='api_production_detail'),
    path('api/verifier-stock/<int:menu_id>/', views.api_verifier_stock, name='api_verifier_stock'),
    path('api/stock/menu/<int:menu_id>/', views.api_stock_menu, name='api_stock_menu'),
    
    # ========== API RECETTES ==========
    path('api/produits/', views.api_produits, name='api_produits'),
    path('api/statistiques/', views.api_statistiques, name='api_statistiques'),
    path('api/dashboard/', views.api_dashboard, name='api_dashboard'),
    path('api/menu/', views.get_menu_pos_api, name='api_menu'),
    path('api/recettes/liste/', views.api_liste_recettes, name='api_liste_recettes'),
    path('api/recettes/disponibles/', views.api_recettes_disponibles, name='api_recettes_disponibles'),
    path('api/recette/<str:recette_id>/menus/', views.api_recette_menus, name='api_recette_menus'),
    path('api/recette/<str:recette_id>/modifier/', views.api_recette_modifier, name='api_recette_modifier_recette'),
    path('api/recettes/<str:recette_id>/production/', views.production_possible_api, name='production_possible_api'),
    path('api/recette/<str:recette_id>/cout/', views.api_recette_cout, name='api_recette_cout'),
    path('api/recette/<str:recette_id>/ingredients/save/', views.api_save_recette_ingredients, name='api_save_recette_ingredients'),
    path('api/recette/<str:recette_id>/etapes/save/', views.api_save_recette_etapes, name='api_save_recette_etapes'),
    path('api/recette/<str:recette_id>/ingredients/', views.api_get_recette_ingredients, name='api_get_recette_ingredients'),
    path('api/recette/<str:recette_id>/etapes/', views.api_get_recette_etapes, name='api_get_recette_etapes'),
    
    # ========== CUISINE (reçoit commandes de POS) ==========
    path('cuisine/', views.cuisine_dashboard, name='cuisine_dashboard'),
    path('api/cuisine/commandes/', views.api_cuisine_commandes, name='api_cuisine_commandes'),
    path('api/cuisine/commande/<str:commande_id>/statut/', views.api_cuisine_changer_statut, name='api_cuisine_changer_statut'),
    path('api/cuisine/historique/', views.api_cuisine_historique, name='api_cuisine_historique'),
    path('api/cuisine/commande/<str:commande_id>/', views.api_cuisine_commande_detail, name='api_cuisine_commande_detail'),
    
    
    # apps/restaurant/urls.py - AJOUTER
    path('api/cuisine/commande/<str:commande_id>/ingredients/', views.api_commande_ingredients, name='api_commande_ingredients'),
    path('api/cuisine/commande/<str:commande_id>/lancer/', views.api_lancer_cuisson, name='api_lancer_cuisson'),
    
]



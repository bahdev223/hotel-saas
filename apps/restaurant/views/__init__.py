# apps/restaurant/views/__init__.py
from .dashboard import dashboard
from .file_attente import file_attente
from .produits import produits_stock, entree_stock, mouvement_stock, ajouter_produit, modifier_produit, supprimer_produit, transfert_central_restaurant, api_ajouter_produit, api_produit_infos, api_modifier_produit, api_entree_stock, api_liste_produits_stock, api_supprimer_produit
from .recettes import (
    recettes_liste, recette_detail, recette_ajouter, recette_modifier,
    recette_supprimer, recette_dupliquer, calcul_cout,
    production_possible_api, get_menu_pos_api,
    api_liste_recettes, api_recette_menus, api_recette_modifier,
)

from .api import (
    api_produits, 
    api_statistiques,
    api_dashboard,
    api_recette_cout,
    api_recette_production,
    api_save_recette_ingredients,
    api_save_recette_etapes,
    api_get_recette_ingredients,
    api_get_recette_etapes,
    api_recettes_disponibles,
    api_save_menu_composition,
)

from .cuisine import (
    cuisine_dashboard,
    api_cuisine_commandes,
    api_cuisine_changer_statut,
    api_cuisine_historique,
    api_cuisine_commande_detail,
    api_commande_ingredients,      # ← AJOUTER
    api_lancer_cuisson,            # ← AJOUTER
)

from .menus import (
    menus_liste, 
    menu_composer,
    api_menu_calculer_prix,
    api_menu_get,
    api_menu_lignes,
    api_menu_recettes,
    api_menu_ajouter,
    api_menu_modifier,
    api_menu_ajouter_recette,
    api_menu_supprimer_ligne,
    api_menu_supprimer,
    api_menus_pos,
    api_menu_detail
)

from .production import (
    production_dashboard,
    production_liste,
    production_detail,
    api_produire,
    api_annuler_production,
    api_verifier_stock,
    api_historique_production,
    api_production_detail,
    api_stock_menu,
)


__all__ = [
    # Dashboard
    'dashboard',
    
    # File d'attente
    'file_attente',
    
    # Produits
    'produits_stock',
    'entree_stock',
    'mouvement_stock',
    'ajouter_produit',
    'modifier_produit',
    'supprimer_produit',
    'transfert_central_restaurant',
    'api_ajouter_produit',
    'api_produit_infos',
    'api_modifier_produit',
    'api_entree_stock',
    'api_liste_produits_stock',
    'api_supprimer_produit',
    
    # Recettes
    'recettes_liste',
    'recette_detail', 
    'recette_ajouter', 
    'recette_modifier',
    'recette_supprimer',
    'recette_dupliquer', 
    'calcul_cout',
    'production_possible_api', 
    'get_menu_pos_api',
    'api_liste_recettes',
    'api_recette_menus',
    'api_recette_modifier',
    
    # API générales
    'api_produits', 
    'api_statistiques',
    'api_dashboard',
    'api_recette_cout',
    'api_recette_production',
    'api_save_recette_ingredients',
    'api_save_recette_etapes',
    'api_get_recette_ingredients',
    'api_get_recette_etapes',
    'api_recettes_disponibles',
    'api_save_menu_composition',
    
    # Cuisine
    'cuisine_dashboard',
    'api_cuisine_commandes',
    'api_cuisine_changer_statut',
    'api_cuisine_historique',
    'api_cuisine_commande_detail',
    'api_commande_ingredients',      # ← AJOUTER
    'api_lancer_cuisson',            # ← AJOUTER
    
    # Menus
    'menus_liste',
    'menu_composer',
    'api_menu_calculer_prix',
    'api_menu_get',
    'api_menu_lignes',
    'api_menu_recettes',
    'api_menu_ajouter',
    'api_menu_modifier',
    'api_menu_ajouter_recette',
    'api_menu_supprimer_ligne',
    'api_menu_supprimer',
    'api_menus_pos',
    'api_menu_detail',
    
    # Production
    'production_dashboard',
    'production_liste',
    'production_detail',
    'api_produire',
    'api_annuler_production',
    'api_verifier_stock',
    'api_historique_production',
    'api_production_detail',
    'api_stock_menu',
]

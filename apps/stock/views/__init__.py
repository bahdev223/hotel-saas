# apps/stock/views/__init__.py
from .dashboard import dashboard
from .produits import (
    liste_produits, ajouter_produit, api_ajouter_produit,
    modifier_produit, supprimer_produit, detail_produit, modifier_prix_produit
)
from .mouvements import (
    liste_mouvements, entree_stock, sortie_stock
)
from .transferts import (
    transfert_produits, liste_transferts, api_transfert_entrepot,
    api_transfert_bar, api_transfert_restaurant, api_annuler_transfert,
)
from .entrepots import (
    liste_entrepots, ajouter_entrepot, detail_entrepot, modifier_entrepot,
    api_supprimer_stock_entrepot
)
from .entrees import (  # 🔥 NOUVEAU
    liste_entrees,
    api_liste_entrees,
    api_ajouter_entree
)

from .achats import (
    liste_achats,
    api_liste_achats,
    api_creer_achat,
)

from .api import (
    api_produit_stock_converti, api_recherche_code_barre,
    api_modifier_image_produit, api_supprimer_image_produit,
    api_produit_infos, api_produit_stock,
    api_stock_by_entrepot_produit, api_ajouter_entrepot,
    api_modifier_produit, api_supprimer_produit,
    api_liste_produits, api_liste_mouvements, api_ajouter_sortie,
    api_liste_transferts, api_effectuer_transfert, api_liste_motifs,
    api_liste_entrepots, api_detail_entrepot_stocks,
    api_notifications_stock,
    api_liste_domaines, api_liste_categories,
)


from .fournisseurs import (
    liste_fournisseurs,
    detail_fournisseur,
    api_liste_fournisseurs,
    api_detail_fournisseur,
)

from .inventaire import liste_inventaires, creer_inventaire, detail_inventaire, supprimer_inventaire, api_mettre_a_jour_ligne, api_lignes_inventaire, api_valider_inventaire
from .pertes import liste_pertes, api_declarer_perte 

__all__ = [
    'dashboard',
    'liste_produits', 'ajouter_produit', 'api_ajouter_produit',
    'modifier_produit', 'supprimer_produit', 'detail_produit',
    'liste_mouvements', 'entree_stock', 'sortie_stock',
    'transfert_produits', 'liste_transferts', 'api_transfert_entrepot',
    'api_transfert_bar', 'api_transfert_restaurant', 
    'liste_entrepots', 'ajouter_entrepot', 'detail_entrepot', 'modifier_entrepot',
    'liste_fournisseurs',
    'detail_fournisseur',
    'api_detail_fournisseur',
    'liste_inventaires',
    'creer_inventaire',
    'detail_inventaire',
    'api_mettre_a_jour_ligne',
    'api_valider_inventaire',
    'liste_pertes',
    'api_declarer_perte',
    'api_ajouter_produit',
    # 🔥 NOUVEAU
    'liste_entrees',
    'api_liste_entrees',
    'api_ajouter_entree',
    'api_modifier_produit',
    'api_supprimer_produit',
    'modifier_prix_produit',
    # SPA endpoints
    'api_liste_produits',
    'api_liste_mouvements',
    'api_liste_motifs',
    'api_ajouter_sortie',
    'api_liste_transferts',
    'api_effectuer_transfert',
    'api_annuler_transfert',
    'api_liste_entrepots',
    'api_detail_entrepot_stocks',
    'liste_achats',
    'api_liste_achats',
    'api_creer_achat',
    'api_notifications_stock',
    'api_liste_domaines',
    'api_liste_categories',
]

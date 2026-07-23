from .stats_service import get_occupation, get_commandes_en_cours, get_alertes_stock, get_reservations_aujourdhui
from .ca_service import (
    get_ca_jour, get_ca_7_jours, get_ca_par_categorie,
    get_ca_hotel, get_ca_brasserie, get_ca_restaurant,
    get_ca_mensuel_par_categorie, get_ca_semaine, get_ca_mois,
    get_repartition_ca_7j, get_charges_par_domaine,
)
from .produits_service import get_top_produits, get_top_produits_par_entrepot
from .activites_service import get_activites_recentes, get_activites_brasserie

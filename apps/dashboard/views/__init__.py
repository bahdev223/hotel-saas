# apps/dashboard/views/__init__.py
from .home import home, index
from .patron import patron_dashboard
from .widgets import widget_data
from .brasserie import brasserie_dashboard, brasserie_produits, brasserie_ajouter_api, brasserie_modifier_api, brasserie_modifier_stock_api, brasserie_supprimer

__all__ = ['home', 'index', 'patron_dashboard', 'widget_data', 'brasserie_dashboard', 'brasserie_produits', 'brasserie_ajouter_api', 'brasserie_modifier_api', 'brasserie_modifier_stock_api', 'brasserie_supprimer']
# apps/restaurant/services/__init__.py

"""
Services du module Restaurant
Centralise la logique métier (menus, recettes, production, stock, consommation)
"""

# Import lazy (évite les imports circulaires)
from .menu_service import MenuService
from .recette_service import RecetteService
from .production_service import *
from .stock_service import StockService
from .consumption_service import RestaurantConsumptionService

__all__ = [
    "MenuService",
    "RecetteService",
    "ProductionService",
    "StockService",
    "RestaurantConsumptionService",
]
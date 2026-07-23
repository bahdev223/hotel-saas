# apps/restaurant/services/menu_service.py
from django.db import transaction
from decimal import Decimal
import uuid
from ..models import MenuModel, LigneMenuModel
from apps.stock.models import Produit, StockEntrepot


class MenuService:
    """Service de gestion des menus"""
    
    @staticmethod
    def calculer_cout_revient(menu, produits_dict=None):
        """Calcule le coût de revient d'un menu"""
        produits_dict = produits_dict or {}
        total = Decimal('0')
        
        for ligne in menu.lignes.all():
            if ligne.type_ligne != 'SUPPLEMENT':
                total += ligne.get_cout(produits_dict)
        
        return total
    
    @staticmethod
    def calculer_marge(menu, produits_dict=None):
        """Calcule la marge d'un menu"""
        cout = MenuService.calculer_cout_revient(menu, produits_dict)
        return menu.prix_vente - cout
    
    @staticmethod
    def verifier_disponibilite(menu, entrepot):
        """Vérifie si un menu peut être servi"""
        from .recette_service import RecetteService
        
        for ligne in menu.lignes.filter(type_ligne='FIXE'):
            verification = RecetteService.verifier_disponibilite(ligne.recette, entrepot)
            if not verification['disponible']:
                return False
        return True
    
    @staticmethod
    @transaction.atomic
    def dupliquer_menu(menu, nouveau_code, nouveau_nom):
        """Duplique un menu existant"""
        nouveau_menu = MenuModel.objects.create(
            code=nouveau_code,
            nom=nouveau_nom,
            type_menu=menu.type_menu,
            prix_vente=menu.prix_vente,
            description=menu.description,
            actif=True
        )
        
        for ligne in menu.lignes.all():
            LigneMenuModel.objects.create(
                id=str(uuid.uuid4()),
                menu=nouveau_menu,
                recette=ligne.recette,
                groupe=ligne.groupe,
                type_ligne=ligne.type_ligne,
                quantite=ligne.quantite,
                prix_supplement=ligne.prix_supplement
            )
        
        return nouveau_menu
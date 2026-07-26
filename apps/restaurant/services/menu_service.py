# apps/restaurant/services/menu_service.py
from collections import defaultdict
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

    @staticmethod
    def valider_choix_menu(menu, choix_list):
        """Valide que les choix respectent les contraintes min/max par groupe.

        choix_list = [{'groupe': 'ENTREE', 'recette_id': '...'}, ...]
        Retourne {'valid': True} ou {'valid': False, 'errors': [...]}
        """
        from collections import Counter
        choix_par_groupe = Counter(c.get('groupe') for c in choix_list)

        groupes_config = {}
        for ligne in menu.lignes.filter(type_ligne='CHOIX'):
            if ligne.groupe not in groupes_config:
                groupes_config[ligne.groupe] = {
                    'min': ligne.min_choix,
                    'max': ligne.max_choix,
                    'options': set(),
                }
            groupes_config[ligne.groupe]['options'].add(ligne.recette_id)

        errors = []
        for groupe, cfg in groupes_config.items():
            nb = choix_par_groupe.get(groupe, 0)
            if nb < cfg['min']:
                errors.append(
                    f"{groupe}: minimum {cfg['min']} choix requis, {nb} fourni(s)"
                )
            if nb > cfg['max']:
                errors.append(
                    f"{groupe}: maximum {cfg['max']} choix autorisé(s), {nb} fourni(s)"
                )
            for c in choix_list:
                if c.get('groupe') == groupe and c.get('recette_id') not in cfg['options']:
                    errors.append(
                        f"{groupe}: la recette {c.get('recette_id')} n'est pas une option valide"
                    )

        if errors:
            return {'valid': False, 'errors': errors}
        return {'valid': True}
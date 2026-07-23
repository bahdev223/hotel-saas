# apps/seed_menus.py
import os
import django
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
django.setup()

from decimal import Decimal
from apps.restaurant.models import MenuModel


def importer_menus():
    print("\n" + "="*60)
    print("🍽️ IMPORTATION DES MENUS")
    print("="*60 + "\n")
    
    menus = [
        # Plats cuisinés
        ("PIZZA001", "Pizza Margherita", 3500),
        ("PIZZA002", "Pizza Pepperoni", 4500),
        ("PIZZA003", "Pizza 4 Fromages", 5000),
        ("KFC001", "KFC (Poulet frit)", 3000),
        ("CHARW001", "Charwarma viande", 2500),
        ("CHARW002", "Charwarma poulet", 2500),
        ("BURGER001", "Cheeseburger", 2500),
        ("BURGER002", "Double Cheeseburger", 3500),
        ("PASTA001", "Spaghetti bolognaise", 4000),
        ("PASTA002", "Spaghetti carbonara", 4500),
        
        # Menus complets
        ("MENU001", "Menu Déjeuner (Plat + Boisson)", 5000),
        ("MENU002", "Menu Soir (Entrée + Plat + Dessert)", 8500),
        ("MENU003", "Menu Enfant", 3500),
    ]
    
    for code, nom, prix in menus:
        menu, created = MenuModel.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'prix_vente': Decimal(prix),
                'visible_dans_pos': True,
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom} ({prix} FCFA)")
    
    total_menus = MenuModel.objects.count()
    print(f"\n✅ Total menus: {total_menus}")
    print("\n🎉 IMPORTATION DES MENUS TERMINÉE !")


if __name__ == "__main__":
    importer_menus()
    
    
    
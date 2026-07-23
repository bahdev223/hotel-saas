# apps/seed_recipes.py
import os
import django
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
django.setup()

from decimal import Decimal
import uuid
from apps.restaurant.models import RecetteModel, IngredientModel
from apps.stock.models import Produit


def creer_recette(nom, type_recette, prix, ingredients):
    """Crée une recette avec ses ingrédients"""
    
    recette, created = RecetteModel.objects.get_or_create(
        nom=nom,
        defaults={
            'type_recette': type_recette,
            'prix_vente': Decimal(prix),
            'temps_preparation_minutes': 15,
            'actif': True,
            'visible_dans_pos': True
        }
    )
    
    if created:
        print(f"  ✅ Recette créée: {nom}")
        
        # Ajouter les ingrédients
        for ing_data in ingredients:
            produit = Produit.objects.filter(code=ing_data['code']).first()
            if produit:
                IngredientModel.objects.create(
                    id=str(uuid.uuid4())[:8],
                    recette=recette,
                    produit=produit,
                    quantite=ing_data['quantite'],
                    unite=ing_data['unite'],
                    type_ingredient='DEDUIRE'
                )
                print(f"      - {ing_data['quantite']} x {produit.nom}")
    else:
        print(f"  ⏭️ Recette existe déjà: {nom}")
    
    return recette


def importer_recettes():
    print("\n" + "="*60)
    print("🍳 IMPORTATION DES RECETTES (PLATS PRÉPARÉS)")
    print("="*60 + "\n")
    
    # Pizza
    creer_recette(
        nom="Pizza",
        type_recette='PLAT',
        prix=4000,
        ingredients=[
            {'code': 'FARINE001', 'quantite': 0.2, 'unite': 'kg'},
            {'code': 'FROMAGE001', 'quantite': 0.1, 'unite': 'kg'},
            {'code': 'SAUCE001', 'quantite': 0.05, 'unite': 'l'},
        ]
    )
    
    # Brochettes
    creer_recette(
        nom="Brochettes (3 pièces)",
        type_recette='PLAT',
        prix=1500,
        ingredients=[
            {'code': 'VIANDE001', 'quantite': 0.3, 'unite': 'kg'},
            {'code': 'HUILE001', 'quantite': 0.05, 'unite': 'l'},
        ]
    )
    
    # Spaghetti bolognaise
    creer_recette(
        nom="Spaghetti bolognaise",
        type_recette='PLAT',
        prix=2000,
        ingredients=[
            {'code': 'FARINE001', 'quantite': 0.2, 'unite': 'kg'},
            {'code': 'VIANDE001', 'quantite': 0.15, 'unite': 'kg'},
            {'code': 'SAUCE001', 'quantite': 0.1, 'unite': 'l'},
        ]
    )
    
    # Poulet braisé
    creer_recette(
        nom="Poulet braisé",
        type_recette='PLAT',
        prix=3500,
        ingredients=[
            {'code': 'POULET001', 'quantite': 0.5, 'unite': 'kg'},
            {'code': 'HUILE001', 'quantite': 0.1, 'unite': 'l'},
        ]
    )
    
    # Riz sauce gombo
    creer_recette(
        nom="Riz sauce gombo",
        type_recette='PLAT',
        prix=2500,
        ingredients=[
            {'code': 'RIZ001', 'quantite': 0.2, 'unite': 'kg'},
            {'code': 'GOMBO001', 'quantite': 0.1, 'unite': 'kg'},
            {'code': 'HUILE001', 'quantite': 0.05, 'unite': 'l'},
            {'code': 'SEL001', 'quantite': 0.005, 'unite': 'kg'},
        ]
    )
    
    # Omelette
    creer_recette(
        nom="Omelette",
        type_recette='PLAT',
        prix=1500,
        ingredients=[
            {'code': 'OIGNON001', 'quantite': 0.05, 'unite': 'kg'},
        ]
    )
    
    # Statistiques
    print("\n" + "="*60)
    print("📊 STATISTIQUES")
    print("="*60)
    
    total_recettes = RecetteModel.objects.filter(actif=True).count()
    print(f"✅ Total recettes créées: {total_recettes}")
    
    print("\n🎉 IMPORTATION TERMINÉE !")


if __name__ == "__main__":
    importer_recettes()
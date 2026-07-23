# apps/seed_products.py
import os
import django
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
django.setup()

from decimal import Decimal
from apps.stock.models import Produit, CategorieProduit, Entrepot, StockEntrepot
from django.db import models


def get_or_create_categorie(nom):
    cat, created = CategorieProduit.objects.get_or_create(nom=nom, defaults={'actif': True})
    if created:
        print(f"  📁 Catégorie créée: {nom}")
    return cat


def importer_produits():
    print("\n" + "="*60)
    print("🚀 IMPORTATION DES PRODUITS")
    print("="*60 + "\n")
    
    entrepot, _ = Entrepot.objects.get_or_create(
        code='RESTAURANT',
        defaults={'nom': 'Restaurant Principal', 'type_entrepot': 'RESTAURANT', 'actif': True}
    )
    
    # ========== 1. MARCHANDISES (vendables directement) ==========
    print("📦 1. MARCHANDISES (vente directe)")
    cat_marchandises = get_or_create_categorie('Marchandises')
    
    marchandises = [
        # Boissons
        ("COC001", "Coca-Cola 33cl", 500, True),
        ("FAN001", "Fanta Orange 33cl", 500, True),
        ("SPR001", "Sprite 33cl", 500, True),
        ("EAU001", "Eau minérale 50cl", 400, True),
        ("EAU002", "Eau minérale 1.5L", 800, True),
        ("JUS001", "Jus d'orange", 800, True),
        ("BIS001", "Bissap", 500, True),
        
        # Bières
        ("BAVGRD001", "Grande BAV 8.6°", 1500, True),
        ("BAVPTE001", "Petite BAV 8.6°", 1000, True),
        ("CASTGRD001", "Grande Castel", 1500, True),
        ("CASTPTE001", "Petite Castel", 1000, True),
        ("HEINB001", "Heineken bouteille", 1500, True),
        ("GUINB001", "Guiness bouteille", 1500, True),
        
        # Cafés
        ("CAF001", "Café Nespresso (moins fort)", 750, True),
        ("CAF002", "Café Nespresso (plus fort)", 750, True),
        
        # Snacks
        ("CHARW001", "Charwarma viande", 1500, True),
        ("CHARW002", "Charwarma poulet", 6000, True),
        ("PIZZA001", "Pizza", 500, True),  # Simple pizza, pas un menu
    ]
    
    for code, nom, prix, vendable in marchandises:
        produit, created = Produit.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'categorie': cat_marchandises,
                'type_article': 'MARCHANDISE',
                'est_vendable': vendable,
                'unite_base': 'piece',
                'prix_achat': Decimal(prix) * Decimal('0.6'),
                'prix_vente': Decimal(prix) if vendable else 0,
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom}")
        
        stock, _ = StockEntrepot.objects.get_or_create(
            entrepot=entrepot,
            produit=produit,
            defaults={'quantite': 100}
        )
    
    # ========== 2. MATIÈRES PREMIÈRES (non vendables directement) ==========
    print("\n🥩 2. MATIÈRES PREMIÈRES (pour cuisine)")
    cat_matieres = get_or_create_categorie('Matières premières')
    
    matieres = [
        ("RIZ001", "Riz blanc", 500, False),
        ("VIANDE001", "Viande de bœuf", 3000, False),
        ("POULET001", "Poulet entier", 3500, False),
        ("POISSON001", "Poisson frais", 2500, False),
        ("OIGNON001", "Oignon", 300, False),
        ("TOMATE001", "Tomate", 400, False),
        ("HUILE001", "Huile végétale", 1200, False),
        ("GOMBO001", "Gombo", 800, False),
        ("PIMENT001", "Piment", 200, False),
        ("SEL001", "Sel", 100, False),
        ("FARINE001", "Farine", 400, False),
        ("FROMAGE001", "Fromage", 2000, False),
        ("SAUCE001", "Sauce tomate", 500, False),
    ]
    
    for code, nom, prix, vendable in matieres:
        produit, created = Produit.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'categorie': cat_matieres,
                'type_article': 'MATIERE_PREMIERE',
                'est_vendable': vendable if vendable else False,
                'unite_base': 'kg' if 'Riz' in nom or 'Viande' in nom else 'piece',
                'prix_achat': Decimal(prix),
                'prix_vente': Decimal(prix) if vendable else 0,
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom}")
        
        stock, _ = StockEntrepot.objects.get_or_create(
            entrepot=entrepot,
            produit=produit,
            defaults={'quantite': 50}
        )
    
    # ========== 3. CONSOMMABLES ==========
    print("\n📦 3. CONSOMMABLES")
    cat_consommables = get_or_create_categorie('Consommables')
    
    consommables = [
        ("PAIN001", "Pain hamburger", 150, False),
        ("MAYO001", "Mayonnaise", 500, False),
        ("KETCHUP001", "Ketchup", 500, False),
        ("BARQUETTE001", "Barquette plastique", 100, False),
        ("SERVIETTE001", "Serviette papier", 20, False),
        ("GOBELET001", "Gobelet jetable", 50, False),
    ]
    
    for code, nom, prix, vendable in consommables:
        produit, created = Produit.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'categorie': cat_consommables,
                'type_article': 'CONSOMMABLE',
                'unite_base': 'piece',
                'prix_achat': Decimal(prix),
                'prix_vente': Decimal(prix) if vendable else 0,
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom}")
        
        stock, _ = StockEntrepot.objects.get_or_create(
            entrepot=entrepot,
            produit=produit,
            defaults={'quantite': 200}
        )
    
    # Statistiques
    print("\n" + "="*60)
    print("📊 STATISTIQUES")
    print("="*60)
    
    total_produits = Produit.objects.count()
    total_marchandises = Produit.objects.filter(type_article='MARCHANDISE').count()
    total_matieres = Produit.objects.filter(type_article='MATIERE_PREMIERE').count()
    total_consommables = Produit.objects.filter(type_article='CONSOMMABLE').count()
    
    print(f"✅ Total produits: {total_produits}")
    print(f"   - Marchandises: {total_marchandises}")
    print(f"   - Matières premières: {total_matieres}")
    print(f"   - Consommables: {total_consommables}")
    
    print("\n🎉 IMPORTATION TERMINÉE !")


if __name__ == "__main__":
    importer_produits()
    
    
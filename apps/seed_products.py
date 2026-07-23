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


def get_or_create_categorie(nom):
    cat, created = CategorieProduit.objects.get_or_create(nom=nom, defaults={'actif': True})
    if created:
        print(f"  📁 Catégorie créée: {nom}")
    return cat


def importer_produits():
    print("\n" + "="*60)
    print("🚀 IMPORTATION DES PRODUITS (STOCK)")
    print("="*60 + "\n")
    
    # Utiliser CENTRAL comme entrepôt principal
    central, _ = Entrepot.objects.get_or_create(
        code='CENTRAL',
        defaults={'nom': 'Magasin Central', 'type_entrepot': 'CENTRAL', 'actif': True}
    )
    
    print(f"📦 Stock ajouté dans: {central.nom}")
    
    # ========== 1. MARCHANDISES (vendables directement) ==========
    print("\n📦 1. MARCHANDISES (vente directe)")
    cat_marchandises = get_or_create_categorie('Marchandises')
    
    marchandises = [
        # Boissons
        ("COC001", "Coca-Cola 33cl", 500),
        ("FAN001", "Fanta Orange 33cl", 500),
        ("SPR001", "Sprite 33cl", 500),
        ("EAU001", "Eau minérale 50cl", 400),
        ("EAU002", "Eau minérale 1.5L", 800),
        ("JUS001", "Jus d'orange", 800),
        ("BIS001", "Bissap", 500),
        # Bières
        ("BAVGRD001", "Grande BAV 8.6°", 1500),
        ("BAVPTE001", "Petite BAV 8.6°", 1000),
        ("CASTGRD001", "Grande Castel", 1500),
        ("CASTPTE001", "Petite Castel", 1000),
        ("HEINB001", "Heineken bouteille", 1500),
        ("GUINB001", "Guiness bouteille", 1500),
        # Cafés
        ("CAF001", "Café Nespresso (moins fort)", 750),
        ("CAF002", "Café Nespresso (plus fort)", 750),
        # Eaux
        ("EAUGAZ001", "Eau gazeuse", 500),
        ("TOPAZ001", "Topaz", 400),
    ]
    
    for code, nom, prix in marchandises:
        produit, created = Produit.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'categorie': cat_marchandises,
                'type_article': 'MARCHANDISE',
                'est_vendable': True,
                'unite_base': 'piece',
                'prix_achat': Decimal(prix) * Decimal('0.6'),
                'prix_vente': Decimal(prix),
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom}")
        
        # Stock dans CENTRAL
        stock, _ = StockEntrepot.objects.get_or_create(
            entrepot=central,
            produit=produit,
            defaults={'quantite': 100}
        )
    
    # ========== 2. MATIÈRES PREMIÈRES ==========
    print("\n🥩 2. MATIÈRES PREMIÈRES")
    cat_matieres = get_or_create_categorie('Matières premières')
    
    matieres = [
        ("RIZ001", "Riz blanc", 500),
        ("VIANDE001", "Viande de bœuf", 3000),
        ("POULET001", "Poulet entier", 3500),
        ("POISSON001", "Poisson frais", 2500),
        ("OIGNON001", "Oignon", 300),
        ("TOMATE001", "Tomate", 400),
        ("HUILE001", "Huile végétale", 1200),
        ("GOMBO001", "Gombo", 800),
        ("FARINE001", "Farine", 400),
        ("FROMAGE001", "Fromage", 2000),
        ("SAUCE001", "Sauce tomate", 500),
        ("SEL001", "Sel", 100),
    ]
    
    for code, nom, prix in matieres:
        produit, created = Produit.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'categorie': cat_matieres,
                'type_article': 'MATIERE_PREMIERE',
                'est_vendable': False,
                'unite_base': 'kg' if 'Riz' in nom or 'Viande' in nom else 'piece',
                'prix_achat': Decimal(prix),
                'prix_vente': 0,
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom}")
        
        stock, _ = StockEntrepot.objects.get_or_create(
            entrepot=central,
            produit=produit,
            defaults={'quantite': 50}
        )
    
    # ========== 3. CONSOMMABLES ==========
    print("\n📦 3. CONSOMMABLES")
    cat_consommables = get_or_create_categorie('Consommables')
    
    consommables = [
        ("PAIN001", "Pain hamburger", 150),
        ("BARQUETTE001", "Barquette plastique", 100),
        ("GOBELET001", "Gobelet jetable", 50),
        ("SERVIETTE001", "Serviette papier", 20),
    ]
    
    for code, nom, prix in consommables:
        produit, created = Produit.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'categorie': cat_consommables,
                'type_article': 'CONSOMMABLE',
                'est_vendable': False,
                'unite_base': 'piece',
                'prix_achat': Decimal(prix),
                'prix_vente': 0,
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom}")
        
        stock, _ = StockEntrepot.objects.get_or_create(
            entrepot=central,
            produit=produit,
            defaults={'quantite': 200}
        )
    
    # ========== 4. ALCOOLS ==========
    print("\n🍾 4. ALCOOLS")
    cat_alcools = get_or_create_categorie('Alcools')
    
    alcools = [
        ("WHISKY001", "Johnnie Walker Red Label", 15000),
        ("WHISKY002", "Johnnie Walker Black Label", 25000),
        ("VODKA001", "Vodka", 12000),
        ("RHUM001", "Rhum", 10000),
        ("GIN001", "Gin", 12000),
        ("VIN001", "Vin rouge", 8000),
        ("VIN002", "Vin blanc", 8000),
        ("CHAMP001", "Champagne", 35000),
    ]
    
    for code, nom, prix in alcools:
        produit, created = Produit.objects.get_or_create(
            code=code,
            defaults={
                'nom': nom,
                'categorie': cat_alcools,
                'type_article': 'MARCHANDISE',
                'est_vendable': True,
                'unite_base': 'piece',
                'prix_achat': Decimal(prix) * Decimal('0.7'),
                'prix_vente': Decimal(prix),
                'actif': True
            }
        )
        if created:
            print(f"  ✅ {nom}")
        
        stock, _ = StockEntrepot.objects.get_or_create(
            entrepot=central,
            produit=produit,
            defaults={'quantite': 20}
        )
    
    # Statistiques
    print("\n" + "="*60)
    print("📊 STATISTIQUES PRODUITS")
    print("="*60)
    
    total_produits = Produit.objects.count()
    total_marchandises = Produit.objects.filter(type_article='MARCHANDISE').count()
    total_matieres = Produit.objects.filter(type_article='MATIERE_PREMIERE').count()
    total_consommables = Produit.objects.filter(type_article='CONSOMMABLE').count()
    
    print(f"✅ Total produits: {total_produits}")
    print(f"   - Marchandises (vendables): {total_marchandises}")
    print(f"   - Matières premières: {total_matieres}")
    print(f"   - Consommables: {total_consommables}")
    
    print("\n🎉 IMPORTATION DES PRODUITS TERMINÉE !")


if __name__ == "__main__":
    importer_produits()
    
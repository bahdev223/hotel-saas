# apps/seed_entrepots.py
import os
import django
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(BASE_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
django.setup()

from apps.stock.models import Entrepot


def creer_entrepots():
    print("\n" + "="*60)
    print("🏭 CRÉATION DE L'ENTREPÔT CENTRAL")
    print("="*60 + "\n")
    
    # Créer uniquement l'entrepôt CENTRAL
    central, created = Entrepot.objects.get_or_create(
        code='CENTRAL',
        defaults={
            'nom': 'Magasin Central',
            'type_entrepot': 'CENTRAL',
            'actif': True
        }
    )
    
    if created:
        print(f"✅ Entrepôt CENTRAL créé : {central.nom}")
    else:
        print(f"⚠️ Entrepôt CENTRAL existe déjà : {central.nom}")
    
    print("\n" + "="*60)
    print("📊 RAPPEL")
    print("="*60)
    print("Les autres entrepôts (BAR, RESTAURANT, CUISINE, etc.)")
    print("seront créés par le responsable stock via l'interface.")
    print("\n🎉 INITIALISATION TERMINÉE !")


if __name__ == "__main__":
    creer_entrepots()
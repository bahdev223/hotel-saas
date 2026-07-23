# clean_all.py - À exécuter dans le shell
from apps.stock.models import Produit, Entrepot, StockEntrepot
from apps.restaurant.models import MenuModel, RecetteModel

# Supprimer dans le bon ordre
StockEntrepot.objects.all().delete()
Produit.objects.all().delete()
Entrepot.objects.all().delete()
MenuModel.objects.all().delete()

print("✅ Nettoyage total terminé !")
print(f"Produits restants: {Produit.objects.count()}")
print(f"Entrepôts restants: {Entrepot.objects.count()}")


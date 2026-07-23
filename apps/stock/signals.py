from django.db.models.signals import post_save
from django.dispatch import receiver
from .models.produit import Produit
from .models.entrepot import Entrepot
from .models.stock_entrepot import StockEntrepot


@receiver(post_save, sender=Produit)
def creer_stock_dans_tous_entrepots(sender, instance, created, **kwargs):
    """Quand un nouveau produit est créé, créer StockEntrepot dans TOUS les entrepôts"""
    if not created:
        return
    for entrepot in Entrepot.objects.filter(actif=True):
        StockEntrepot.objects.get_or_create(
            entrepot=entrepot,
            produit=instance,
            defaults={'quantite': 0}
        )


@receiver(post_save, sender=Entrepot)
def creer_tous_produits_dans_entrepot(sender, instance, created, **kwargs):
    """Quand un nouvel entrepôt est créé, créer StockEntrepot pour TOUS les produits"""
    if not created:
        return
    for produit in Produit.objects.filter(actif=True, est_vendable=True):
        StockEntrepot.objects.get_or_create(
            entrepot=instance,
            produit=produit,
            defaults={'quantite': 0}
        )

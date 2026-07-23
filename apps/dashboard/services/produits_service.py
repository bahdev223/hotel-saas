from django.db.models import Sum, F
from apps.pos.models import LigneVente
from apps.stock.models import Produit, StockEntrepot


def get_top_produits(limit=5):
    """Top N produits les plus vendus (via lignes de ventes payées)."""
    top = (
        LigneVente.objects
        .filter(vente__statut='PAYEE', produit__isnull=False)
        .annotate(ligne_total=F('quantite') * F('prix_unitaire'))
        .values('produit__nom')
        .annotate(
            quantite=Sum('quantite'),
            montant=Sum('ligne_total')
        )
        .order_by('-quantite')[:limit]
    )

    return [
        {'nom': t['produit__nom'], 'quantite': float(t['quantite']), 'montant': float(t['montant'])}
        for t in top
    ]


def get_top_produits_par_entrepot(type_entrepot='BAR', limit=5):
    """Top N produits les plus vendus filtrés par entrepôt."""
    from apps.stock.models import Entrepot
    entrepot = Entrepot.objects.filter(type_entrepot=type_entrepot, actif=True).first()
    if not entrepot:
        return []

    produits_ids = StockEntrepot.objects.filter(
        entrepot=entrepot
    ).values_list('produit_id', flat=True)

    top = (
        LigneVente.objects
        .filter(vente__statut='PAYEE', produit_id__in=list(produits_ids))
        .annotate(ligne_total=F('quantite') * F('prix_unitaire'))
        .values('produit__nom')
        .annotate(
            quantite=Sum('quantite'),
            montant=Sum('ligne_total')
        )
        .order_by('-quantite')[:limit]
    )

    return [
        {'nom': t['produit__nom'], 'quantite': float(t['quantite']), 'montant': float(t['montant'])}
        for t in top
    ]

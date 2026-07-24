from datetime import datetime, date, timedelta
from django.db.models import Sum, Count, Q
from apps.hotel.models import UniteModel, LocationModel
from apps.pos.models import Commande, Vente
from apps.stock.models import StockEntrepot, Entrepot


def get_occupation():
    """Taux d'occupation des chambres/hébergements."""
    total = UniteModel.objects.filter(actif=True).count()
    occupees = UniteModel.objects.filter(actif=True, statut='OCCUPEE').count()
    taux = round((occupees / total * 100), 1) if total > 0 else 0
    return {'total': total, 'occupees': occupees, 'taux': taux}


def get_commandes_en_cours():
    """Commandes en attente/préparation/prête par type."""
    from apps.stock.models import Entrepot
    from apps.pos.models import PointVente
    statuts = ['EN_ATTENTE', 'EN_PREPARATION', 'PRETE']
    qs = Commande.objects.filter(statut__in=statuts)

    restaurant = qs.filter(point_vente__type='RESTAURATION').count()
    bar = qs.filter(point_vente__type='BAR').count()
    room_service = qs.filter(point_vente__type='ROOM_SERVICE').count()

    entrepot = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()
    brasserie = 0
    if entrepot:
        from apps.pos.models import PointVenteEntrepot
        pv_ids = list(PointVenteEntrepot.objects.filter(entrepot=entrepot).values_list('point_vente_id', flat=True))
        if pv_ids:
            brasserie = qs.filter(point_vente_id__in=pv_ids).count()
        else:
            brasserie = bar  # fallback

    return {
        'total': restaurant + bar + room_service,
        'restaurant': restaurant,
        'bar': bar,
        'room_service': room_service,
        'brasserie': brasserie,
    }


def get_alertes_stock():
    """Produits en rupture ou sous seuil d'alerte dans tous les entrepôts."""
    alertes_par_entrepot = []
    total_alertes = 0

    for entrepot in Entrepot.objects.filter(actif=True):
        stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit')
        ruptures = [s for s in stocks if s.quantite <= 0]
        alertes = [s for s in stocks if 0 < s.quantite <= (s.produit.seuil_alerte or 5)]
        nb = len(ruptures) + len(alertes)
        if nb > 0:
            alertes_par_entrepot.append({
                'entrepot': entrepot.nom,
                'ruptures': len(ruptures),
                'alertes': len(alertes),
                'total': nb,
            })
            total_alertes += nb

    return {'total': total_alertes, 'par_entrepot': alertes_par_entrepot}


def get_reservations_aujourdhui():
    """Réservations/locations en cours aujourd'hui."""
    aujourdhui = date.today()
    return LocationModel.objects.filter(
        date_debut__date=aujourdhui,
        statut='CONFIRMEE'
    ).count()

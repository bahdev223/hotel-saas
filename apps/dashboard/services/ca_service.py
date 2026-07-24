from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.db.models import Sum, Q
from apps.pos.models import Vente
from apps.hotel.models import LocationModel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ca_ventes_emplacement(jour, emplacements):
    """CA des ventes PAYÉES pour une liste d'emplacements à une date donnée."""
    total = Vente.objects.filter(
        statut='PAYEE',
        created_at__date=jour,
        point_vente__type__in=emplacements
    ).aggregate(total=Sum('montant_total'))['total'] or 0
    return float(total)


def _ca_ventes_brasserie(jour):
    """CA des ventes PAYÉES dont les produits appartiennent à l'entrepôt BRASSERIE.
    Fallback: ventes aux emplacements BAR / TERRASSE / VIP si aucun stock BRASSERIE."""
    from apps.stock.models import Entrepot, StockEntrepot
    from apps.pos.models import LigneVente
    entrepot = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()
    if not entrepot:
        return _ca_ventes_emplacement(jour, ['BAR'])

    # Produits dans l'entrepôt BRASSERIE
    produit_ids = list(StockEntrepot.objects.filter(
        entrepot=entrepot, produit__actif=True
    ).values_list('produit_id', flat=True))

    if not produit_ids:
        return _ca_ventes_emplacement(jour, ['BAR'])

    # Somme des lignes de vente pour ces produits, ventes PAYÉES du jour
    from django.db.models import Sum, F
    total = LigneVente.objects.filter(
        produit_id__in=produit_ids,
        vente__statut='PAYEE',
        vente__created_at__date=jour
    ).aggregate(total=Sum(F('quantite') * F('prix_unitaire')))['total'] or 0
    return float(total)


def _ca_locations(jour):
    """CA des locations (chambres, salles…) pour une date de début donnée."""
    try:
        total = LocationModel.objects.filter(
            date_debut__date=jour,
        ).exclude(statut='ANNULEE').aggregate(total=Sum('montant_total'))['total']
        return float(total or 0)
    except InvalidOperation:
        return 0.0


# ---------------------------------------------------------------------------
# Par catégorie métier  —  Hôtel / Brasserie / Restaurant
# ---------------------------------------------------------------------------

def get_ca_restaurant(jour=None):
    """CA Restaurant pour un jour donné (aujourd'hui par défaut)."""
    jour = jour or date.today()
    return _ca_ventes_emplacement(jour, ['RESTAURATION'])


def get_ca_brasserie(jour=None):
    """CA Brasserie pour un jour donné (aujourd'hui par défaut)."""
    jour = jour or date.today()
    return _ca_ventes_brasserie(jour)


def get_ca_hotel(jour=None):
    """CA Hôtel pour un jour donné (locations chambres + réception + room service)."""
    jour = jour or date.today()
    return _ca_locations(jour) + _ca_ventes_emplacement(jour, ['RECEPTION', 'ROOM_SERVICE'])


def get_ca_par_categorie(jour=None):
    """CA du jour réparti par catégorie : {hotel, brasserie, restaurant}."""
    jour = jour or date.today()
    return {
        'hotel': get_ca_hotel(jour),
        'brasserie': get_ca_brasserie(jour),
        'restaurant': get_ca_restaurant(jour),
    }


def get_ca_jour():
    """CA total du jour (Hôtel + Brasserie + Restaurant)."""
    ca = get_ca_par_categorie()
    return sum(ca.values())


def get_ca_7_jours():
    """CA des 7 derniers jours — chaque jour avec breakdown par catégorie."""
    data = []
    for i in range(6, -1, -1):
        jour = date.today() - timedelta(days=i)
        cats = get_ca_par_categorie(jour)
        data.append({
            'date': jour.strftime('%d/%m'),
            'ca': sum(cats.values()),
            'hotel': cats['hotel'],
            'brasserie': cats['brasserie'],
            'restaurant': cats['restaurant'],
        })
    return data


def get_ca_mensuel_par_categorie():
    """CA des 30 derniers jours avec breakdown Hôtel/Brasserie/Restaurant
    pour un graphique à 3 courbes d'évolution."""
    data = []
    for i in range(29, -1, -1):
        jour = date.today() - timedelta(days=i)
        cats = get_ca_par_categorie(jour)
        data.append({
            'date': jour.strftime('%d/%m'),
            'hotel': cats['hotel'],
            'brasserie': cats['brasserie'],
            'restaurant': cats['restaurant'],
        })
    return data


def get_ca_semaine():
    """CA total des 7 derniers jours avec breakdown par catégorie."""
    total = {'hotel': 0.0, 'brasserie': 0.0, 'restaurant': 0.0}
    for i in range(7):
        jour = date.today() - timedelta(days=i)
        cats = get_ca_par_categorie(jour)
        total['hotel'] += cats['hotel']
        total['brasserie'] += cats['brasserie']
        total['restaurant'] += cats['restaurant']
    total['total'] = sum(total.values())
    return total


def get_ca_mois():
    """CA total des 30 derniers jours avec breakdown par catégorie."""
    total = {'hotel': 0.0, 'brasserie': 0.0, 'restaurant': 0.0}
    for i in range(30):
        jour = date.today() - timedelta(days=i)
        cats = get_ca_par_categorie(jour)
        total['hotel'] += cats['hotel']
        total['brasserie'] += cats['brasserie']
        total['restaurant'] += cats['restaurant']
    total['total'] = sum(total.values())
    return total


def get_repartition_ca_7j():
    """Répartition du CA (7 jours) par catégorie, en FCFA et en pourcentage."""
    total_hotel = total_brasserie = total_restaurant = 0.0
    for i in range(7):
        jour = date.today() - timedelta(days=i)
        cats = get_ca_par_categorie(jour)
        total_hotel += cats['hotel']
        total_brasserie += cats['brasserie']
        total_restaurant += cats['restaurant']
    total = total_hotel + total_brasserie + total_restaurant
    return {
        'hotel': {'montant': total_hotel, 'pct': round(total_hotel / total * 100, 1) if total else 0},
        'brasserie': {'montant': total_brasserie, 'pct': round(total_brasserie / total * 100, 1) if total else 0},
        'restaurant': {'montant': total_restaurant, 'pct': round(total_restaurant / total * 100, 1) if total else 0},
    }


def get_charges_par_domaine():
    """Dépenses par domaine (mois en cours) — valeurs négatives pour calcul résultat."""
    from apps.paiements.models import Paiement
    from datetime import date
    from django.db.models import Sum

    today = date.today()
    first_this_month = today.replace(day=1)

    DOMAINE_MAP = {
        'brasserie': ['BAR'],
        'restaurant': ['RESTAURATION', 'ROOM_SERVICE'],
        'hotel': ['RECEPTION'],
    }

    result = {}
    for domaine, emplacements in DOMAINE_MAP.items():
        total = Paiement.objects.filter(
            sens='SORTIE', statut='VALIDE',
            caisse__point_vente__type__in=emplacements,
            date__date__gte=first_this_month,
            date__date__lte=today,
        ).exclude(type_paiement__in=['TRANSFERT']).aggregate(
            total=Sum('montant')
        )['total'] or 0
        result[domaine] = -float(total)  # négatif pour que CA + dépenses = résultat

    sans_pv = Paiement.objects.filter(
        sens='SORTIE', statut='VALIDE',
        caisse__point_vente__isnull=True,
        date__date__gte=first_this_month,
        date__date__lte=today,
    ).exclude(type_paiement__in=['TRANSFERT']).aggregate(
        total=Sum('montant')
    )['total'] or 0
    result['autres'] = -float(sans_pv)
    return result

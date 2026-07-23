import decimal
from datetime import date, timedelta
from django.utils import timezone
from apps.hotel.models import LocationModel, UniteModel
from apps.pos.models import Commande, Vente
from apps.clients.models import Client


def get_activites_recentes(limit=10):
    """Dernières activités (locations, commandes, ventes)."""
    activites = []
    seuil = timezone.now() - timedelta(hours=24)

    try:
        for loc in LocationModel.objects.filter(
            created_at__gte=seuil
        ).select_related('client', 'unite').order_by('-created_at')[:5]:
            nom = loc.client_nom or (loc.client.nom_complet if loc.client else 'Anonyme')
            activites.append({
                'heure': loc.created_at.strftime('%H:%M'),
                'action': 'Nouvelle réservation' if loc.statut == 'CONFIRMEE' else 'Terminée',
                'detail': f"{loc.unite.nom} - {nom}" if loc.unite else nom,
                'type': 'success' if loc.statut == 'CONFIRMEE' else 'warning',
            })
    except Exception:
        pass

    try:
        for cmd in Commande.objects.filter(
            created_at__gte=seuil
        ).select_related('point_vente').order_by('-created_at')[:5]:
            activites.append({
                'heure': cmd.created_at.strftime('%H:%M'),
                'action': f"Commande {cmd.get_statut_display()}",
                'detail': f"{cmd.point_vente.nom} - {cmd.client_nom or 'Anonyme'} ({cmd.montant_total:,.0f} F)",
                'type': 'info',
            })
    except Exception:
        pass

    try:
        for v in Vente.objects.filter(
            created_at__gte=seuil,
            statut='PAYEE'
        ).select_related('point_vente').order_by('-created_at')[:5]:
            activites.append({
                'heure': v.created_at.strftime('%H:%M'),
                'action': 'Paiement encaissé',
                'detail': f"{v.point_vente.nom} - {v.client_nom or 'Anonyme'} ({v.montant_total:,.0f} F)",
                'type': 'success',
            })
    except Exception:
        pass

    activites.sort(key=lambda a: a['heure'], reverse=True)
    return activites[:limit]


def get_activites_brasserie(limit=10):
    """Dernières activités spécifiques à la brasserie (points de vente liés à l'entrepôt BRASSERIE).
    Fallback: emplacements BAR / TERRASSE / VIP."""
    from apps.stock.models import Entrepot
    from apps.pos.models import PointVente
    emplacements_bar = ['BAR', 'TERRASSE', 'VIP']
    entrepot = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()
    pv_ids = []
    if entrepot:
        pv_ids = list(PointVente.objects.filter(entrepot=entrepot, actif=True).values_list('id', flat=True))

    activites = []
    seuil = timezone.now() - timedelta(hours=24)

    cmd_filter = {'point_vente_id__in': pv_ids, 'created_at__gte': seuil}
    vente_filter = {'point_vente_id__in': pv_ids, 'created_at__gte': seuil, 'statut': 'PAYEE'}
    if not pv_ids:
        cmd_filter = {'point_vente__emplacement__in': emplacements_bar, 'created_at__gte': seuil}
        vente_filter = {'point_vente__emplacement__in': emplacements_bar, 'created_at__gte': seuil, 'statut': 'PAYEE'}

    try:
        for cmd in Commande.objects.filter(**cmd_filter).select_related('point_vente').order_by('-created_at')[:5]:
            activites.append({
                'heure': cmd.created_at.strftime('%H:%M'),
                'action': 'Commande',
                'detail': f"{cmd.point_vente.nom} - {cmd.client_nom or 'Anonyme'} ({cmd.montant_total:,.0f} F)",
                'statut': cmd.get_statut_display(),
                'type': 'info',
            })
    except Exception:
        pass

    try:
        for v in Vente.objects.filter(**vente_filter).select_related('point_vente').order_by('-created_at')[:5]:
            activites.append({
                'heure': v.created_at.strftime('%H:%M'),
                'action': 'Vente',
                'detail': f"{v.point_vente.nom} - {v.client_nom or 'Anonyme'} ({v.montant_total:,.0f} F)",
                'statut': 'Payée',
                'type': 'success',
            })
    except Exception:
        pass

    activites.sort(key=lambda a: a['heure'], reverse=True)
    return activites[:limit]


def get_dernieres_reservations(limit=10):
    """Dernières réservations (locations en cours)."""
    result = []
    try:
        for loc in LocationModel.objects.filter(
            statut='CONFIRMEE'
        ).select_related('client', 'unite').order_by('-date_debut')[:limit]:
            try:
                montant = float(loc.montant_total)
            except (TypeError, ValueError, decimal.InvalidOperation):
                montant = 0
            result.append({
                'id': loc.id,
                'unite': loc.unite.nom if loc.unite else 'N/A',
                'client': loc.client_nom or (loc.client.nom_complet if loc.client else 'Anonyme'),
                'date_debut': loc.date_debut,
                'date_fin': loc.date_fin,
                'montant': montant,
            })
    except Exception:
        return []
    return result

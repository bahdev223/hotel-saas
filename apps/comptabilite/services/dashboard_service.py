from datetime import date, timedelta, datetime
from decimal import Decimal
from django.db.models import Sum, Count
from apps.tresorerie.models import Caisse
from apps.paiements.models import Paiement
from apps.comptabilite.models import CompteClient, CompteFournisseur, ExerciceModel
from apps.dashboard.services.ca_service import get_ca_par_categorie, get_ca_mensuel_par_categorie, get_repartition_ca_7j


def get_tresorerie():
    caisses_physiques = Caisse.objects.filter(actif=True, type_financier='ESPECES')
    caisses_banque = Caisse.objects.filter(actif=True, type_financier='BANQUE')

    total_caisses = sum(c.solde for c in caisses_physiques)
    total_banques = sum(c.solde for c in caisses_banque)

    return {
        'total_caisses': float(total_caisses),
        'total_banques': float(total_banques),
        'total': float(total_caisses + total_banques),
        'caisses': list(caisses_physiques) + list(caisses_banque),
    }


def get_ca_mensuel():
    """CA = ventes validées (commercial), pas les encaissements."""
    from apps.pos.models import Vente

    today = date.today()
    first_this_month = today.replace(day=1)
    first_last_month = (first_this_month - timedelta(days=1)).replace(day=1)

    ca_jour = Vente.objects.filter(
        statut='PAYEE',
        created_at__date=today,
    ).aggregate(total=Sum('montant_total'))['total'] or 0

    ca_mois = Vente.objects.filter(
        statut='PAYEE',
        created_at__date__gte=first_this_month,
        created_at__date__lte=today,
    ).aggregate(total=Sum('montant_total'))['total'] or 0

    ca_mois_dernier = Vente.objects.filter(
        statut='PAYEE',
        created_at__date__gte=first_last_month,
        created_at__date__lt=first_this_month,
    ).aggregate(total=Sum('montant_total'))['total'] or 0

    if ca_mois_dernier > 0:
        evolution = round((float(ca_mois) - float(ca_mois_dernier)) / float(ca_mois_dernier) * 100, 1)
    else:
        evolution = 100 if float(ca_mois) > 0 else 0

    return {
        'ca_jour': float(ca_jour),
        'ca_mois': float(ca_mois),
        'ca_mois_dernier': float(ca_mois_dernier),
        'evolution': evolution,
    }


def get_charges_mensuelles():
    """Charges = sorties de trésorerie réelles (paiements SORTIE)."""
    today = date.today()
    first_this_month = today.replace(day=1)

    charges_jour = Paiement.objects.filter(
        sens='SORTIE',
        statut='VALIDE',
        date__date=today,
    ).exclude(type_paiement__in=['TRANSFERT']).aggregate(
        total=Sum('montant')
    )['total'] or 0

    charges_mois = Paiement.objects.filter(
        sens='SORTIE',
        statut='VALIDE',
        date__date__gte=first_this_month,
        date__date__lte=today,
    ).exclude(type_paiement__in=['TRANSFERT']).aggregate(
        total=Sum('montant')
    )['total'] or 0

    return {
        'charges_jour': float(charges_jour),
        'charges_mois': float(charges_mois),
    }


def get_resultat(ca_mois=None, charges_mois=None):
    if ca_mois is None:
        ca_mois = get_ca_mensuel()['ca_mois']
    if charges_mois is None:
        charges_mois = get_charges_mensuelles()['charges_mois']
    return round(ca_mois - charges_mois, 2)


def get_creances_clients():
    comptes = CompteClient.objects.filter(solde__gt=0)
    total = sum(c.solde for c in comptes)
    return {
        'nombre': comptes.count(),
        'total': float(total),
    }


def get_dettes_fournisseurs():
    comptes = CompteFournisseur.objects.filter(solde__gt=0)
    total = sum(c.solde for c in comptes)
    return {
        'nombre': comptes.count(),
        'total': float(total),
    }


def get_depots_clients():
    total = CompteClient.objects.aggregate(total=Sum('solde'))['total'] or 0
    return float(total)


def get_evolution_ca_30j():
    """Évolution du CA (toutes sources) sur 30 jours via ca_service"""
    return get_ca_mensuel_par_categorie()


def get_ca_par_domaine():
    """Répartition du CA 7j par domaine"""
    return get_repartition_ca_7j()


def get_charges_par_domaine():
    """Dépenses par domaine (via caisse → point_vente → emplacement)"""
    from django.db.models import Sum
    from apps.paiements.models import Paiement

    today = date.today()
    first_this_month = today.replace(day=1)

    DOMAINE_MAP = {
        'brasserie': ['BAR', 'VIP', 'TERRASSE', 'GUICHET'],
        'restaurant': ['RESTAURANT', 'ROOM_SERVICE'],
        'hotel': ['RECEPTION'],
    }

    result = {}
    for domaine, emplacements in DOMAINE_MAP.items():
        total = Paiement.objects.filter(
            sens='SORTIE', statut='VALIDE',
            caisse__point_vente__emplacement__in=emplacements,
            date__date__gte=first_this_month,
            date__date__lte=today,
        ).exclude(type_paiement__in=['TRANSFERT']).aggregate(
            total=Sum('montant')
        )['total'] or 0
        result[domaine] = -float(total)  # négatif pour calcul résultat

    # Dépenses sans point de vente (administratives, etc.)
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


def get_dernieres_operations(limit=10):
    paiements = Paiement.objects.filter(
        statut='VALIDE'
    ).order_by('-date')[:limit]
    data = []
    for p in paiements:
        data.append({
            'id': p.id,
            'reference': p.reference,
            'type': p.get_type_paiement_display(),
            'sens': p.sens,
            'montant': float(p.montant),
            'mode': p.get_mode_display(),
            'date': p.date,
            'client': p.client.nom_complet if p.client else '',
        })
    return data


def get_alertes():
    alerts = []
    from apps.pos.models import SessionCaisse
    from apps.fournisseurs.models import Fournisseur
    from apps.clients.models import Client

    # Sessions non clôturées
    sessions_ouvertes = SessionCaisse.objects.filter(statut='OUVERTE').count()
    if sessions_ouvertes:
        alerts.append({
            'type': 'warning',
            'icon': 'fa-clock',
            'message': f"{sessions_ouvertes} session(s) non clôturée(s)",
        })

    # Clients avec solde négatif (débiteurs)
    clients_deb = CompteClient.objects.filter(solde__lt=0).count()
    if clients_deb:
        total_deb = abs(sum(
            c.solde for c in CompteClient.objects.filter(solde__lt=0)
        ))
        alerts.append({
            'type': 'danger',
            'icon': 'fa-exclamation-triangle',
            'message': f"{clients_deb} client(s) débiteur(s) — {float(total_deb):,.0f} FCFA",
        })

    return alerts

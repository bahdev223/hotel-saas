from apps.hotel.models import LocationModel, Reservation, Sejour
from apps.pos.models import Commande, Vente, LigneVente
from apps.facturation.models import FactureModel
from apps.paiements.models import Paiement
from apps.comptabilite.models import CompteClient
from apps.clients.models import Client
from django.contrib.contenttypes.models import ContentType


def get_client_operations(client_id):
    """Toutes les operations d'un client (locations, commandes, ventes, factures, paiements)."""
    return {
        'locations': _get_locations(client_id),
        'commandes': _get_commandes(client_id),
        'ventes': _get_ventes(client_id),
        'factures': _get_factures(client_id),
        'paiements': _get_paiements(client_id),
    }


def _get_locations(client_id):
    """Historique unifié des séjours/réservations du client, toutes sources
    confondues : ancien flux hotel.LocationModel (encore alimenté par le POS)
    + nouveau flux Reservation/Sejour. Prefixes d'id distincts pour éviter
    toute collision de clé entre tables différentes."""
    resultats = []

    qs_loc = LocationModel.objects.filter(client_id=client_id).select_related('unite').order_by('-created_at')
    for loc in qs_loc:
        resultats.append({
            'id': f'LOC-{loc.id}',
            'type': loc.get_type_location_display(),
            'unite': loc.unite.nom if loc.unite else 'N/A',
            'date_debut': loc.date_debut.isoformat(),
            'date_fin': loc.date_fin.isoformat(),
            'montant': float(loc.montant_total),
            'statut': loc.get_statut_display(),
            'statut_code': loc.statut,
            'date': loc.created_at.isoformat(),
        })

    # Réservations pas encore transformées en séjour (à venir, annulées, no-show).
    # Les réservations transformées sont déjà représentées par leur Sejour ci-dessous.
    qs_res = Reservation.objects.filter(
        client_id=client_id,
    ).exclude(
        statut=Reservation.StatutReservation.TRANSFORMEE,
    ).prefetch_related('chambres_reservees__chambre').order_by('-cree_le')
    for reservation in qs_res:
        chambres = reservation.chambres_reservees.all()
        if not chambres:
            continue
        for rc in chambres:
            resultats.append({
                'id': f'RES-{rc.id}',
                'type': f'Réservation ({reservation.code})',
                'unite': rc.chambre.nom if rc.chambre else 'N/A',
                'date_debut': reservation.date_arrivee_prevue.isoformat(),
                'date_fin': reservation.date_depart_prevue.isoformat(),
                'montant': float(rc.montant_total),
                'statut': reservation.get_statut_display(),
                'statut_code': reservation.statut,
                'date': reservation.cree_le.isoformat(),
            })

    qs_sej = Sejour.objects.filter(client_id=client_id).select_related('chambre').order_by('-cree_le')
    for sejour in qs_sej:
        resultats.append({
            'id': f'SEJ-{sejour.id}',
            'type': f'Séjour ({sejour.code})',
            'unite': sejour.chambre.nom if sejour.chambre else 'N/A',
            'date_debut': sejour.date_arrivee.isoformat(),
            'date_fin': sejour.date_depart.isoformat() if sejour.date_depart else None,
            'montant': float(sejour.montant_total),
            'statut': sejour.get_statut_display(),
            'statut_code': sejour.statut,
            'date': sejour.cree_le.isoformat(),
        })

    resultats.sort(key=lambda r: r['date'], reverse=True)
    return resultats


def _get_commandes(client_id):
    qs = Commande.objects.filter(client_id=client_id).select_related('point_vente').order_by('-created_at')
    return [
        {
            'id': cmd.id,
            'numero': cmd.numero,
            'point_vente': cmd.point_vente.nom if cmd.point_vente else 'N/A',
            'type': cmd.get_type_commande_display(),
            'montant': float(cmd.montant_total),
            'statut': cmd.get_statut_display(),
            'statut_code': cmd.statut,
            'payee': cmd.vente is not None,
            'date': cmd.created_at.isoformat(),
        }
        for cmd in qs
    ]


def _get_ventes(client_id):
    qs = Vente.objects.filter(client_id=client_id).select_related('point_vente').order_by('-created_at')
    return [
        {
            'id': v.id,
            'numero': v.numero,
            'point_vente': v.point_vente.nom if v.point_vente else 'N/A',
            'montant': float(v.montant_total),
            'mode_paiement': v.get_mode_paiement_display(),
            'statut': v.get_statut_display(),
            'date': v.created_at.isoformat(),
        }
        for v in qs
    ]


def _get_factures(client_id):
    qs = FactureModel.objects.filter(client_id=client_id).order_by('-created_at')
    return [
        {
            'id': f.id,
            'numero': f.numero,
            'type': f.type_facture,
            'montant': float(f.montant_total),
            'paye': float(f.total_paye),
            'reste': float(f.reste_a_payer),
            'statut': f.get_statut_display(),
            'statut_code': f.statut,
            'date': f.created_at.isoformat(),
        }
        for f in qs
    ]


def _get_paiements(client_id):
    """Paiements lies au client via le champ direct client ou via GenericForeignKey."""
    qs = Paiement.objects.filter(client_id=client_id).order_by('-date')
    return [
        {
            'id': p.id,
            'reference': p.reference,
            'montant': float(p.montant),
            'sens': p.get_sens_display(),
            'sens_code': p.sens,
            'mode': p.get_mode_display(),
            'statut': p.get_statut_display(),
            'date': p.date.isoformat(),
        }
        for p in qs
    ]


def get_client_solde_movements(client_id):
    """Mouvements du solde du client : ecritures CompteClient et totaux paiements."""
    comptes = CompteClient.objects.filter(client_id=client_id).select_related('exercice').order_by('-exercice__date_debut')
    mouvements = [
        {
            'exercice': c.exercice.code,
            'exercice_label': str(c.exercice),
            'solde': float(c.solde),
            'ecart_lettrage': float(c.ecart_lettrage),
            'mis_a_jour': c.updated_at.isoformat(),
        }
        for c in comptes
    ]

    # Totaux paiements
    total_depots = sum(
        p.montant for p in Paiement.objects.filter(
            client_id=client_id, sens='ENTREE', statut='VALIDE'
        )
    )
    total_retraits = sum(
        p.montant for p in Paiement.objects.filter(
            client_id=client_id, sens='SORTIE', statut='VALIDE'
        )
    )

    return {
        'comptes': mouvements,
        'total_depots': float(total_depots),
        'total_retraits': float(total_retraits),
        'solde_calculé': float(total_depots - total_retraits),
    }

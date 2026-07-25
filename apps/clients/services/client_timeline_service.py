"""Chronologie unifiée et indicateurs commerciaux d'un client.

Fusionne toutes les opérations (réservations, séjours, anciennes locations,
commandes, ventes, factures, paiements) en une seule liste triée par date,
au format commun consommé par la fiche client.
"""
from decimal import Decimal

from django.utils import timezone

from apps.hotel.models import LocationModel, Reservation, Sejour
from apps.pos.models import Commande, Vente
from apps.facturation.models import FactureModel
from apps.paiements.models import Paiement


class ClientTimelineService:

    @classmethod
    def get_timeline(cls, client_id, limit=None):
        """Liste unifiée d'événements {type, titre, reference, montant,
        statut, statut_code, date, description}, triée du plus récent au
        plus ancien. `limit` optionnel pour tronquer."""
        evenements = []

        for reservation in Reservation.objects.filter(client_id=client_id):
            evenements.append({
                'type': 'RESERVATION',
                'titre': 'Réservation',
                'reference': reservation.code,
                'montant': float(reservation.montant_total_estime),
                'statut': reservation.get_statut_display(),
                'statut_code': reservation.statut,
                'date': reservation.cree_le,
                'description': (
                    f"Arrivée {reservation.date_arrivee_prevue.strftime('%d/%m/%Y')} · "
                    f"{reservation.duree_nuits} nuit(s)"
                ),
            })

        for sejour in Sejour.objects.filter(client_id=client_id).select_related('chambre'):
            evenements.append({
                'type': 'SEJOUR',
                'titre': 'Séjour' + (f" — {sejour.chambre.nom}" if sejour.chambre else ''),
                'reference': sejour.code,
                'montant': float(sejour.montant_total),
                'statut': sejour.get_statut_display(),
                'statut_code': sejour.statut,
                'date': sejour.date_arrivee,
                'description': (
                    f"Check-in {sejour.date_arrivee.strftime('%d/%m/%Y %H:%M')}"
                    + (f" · Check-out {sejour.date_depart.strftime('%d/%m/%Y %H:%M')}" if sejour.date_depart else '')
                ),
            })

        for loc in LocationModel.objects.filter(client_id=client_id).select_related('unite'):
            evenements.append({
                'type': 'LOCATION',
                'titre': 'Location' + (f" — {loc.unite.nom}" if loc.unite else ''),
                'reference': loc.id,
                'montant': float(loc.montant_total),
                'statut': loc.get_statut_display(),
                'statut_code': loc.statut,
                'date': loc.created_at,
                'description': loc.get_type_location_display(),
            })

        for cmd in Commande.objects.filter(client_id=client_id).select_related('point_vente'):
            evenements.append({
                'type': 'COMMANDE',
                'titre': 'Commande' + (f" — {cmd.point_vente.nom}" if cmd.point_vente else ''),
                'reference': cmd.numero,
                'montant': float(cmd.montant_total),
                'statut': cmd.get_statut_display(),
                'statut_code': cmd.statut,
                'date': cmd.created_at,
                'description': cmd.get_type_commande_display(),
            })

        for vente in Vente.objects.filter(client_id=client_id).select_related('point_vente'):
            evenements.append({
                'type': 'VENTE',
                'titre': 'Vente' + (f" — {vente.point_vente.nom}" if vente.point_vente else ''),
                'reference': vente.numero,
                'montant': float(vente.montant_total),
                'statut': vente.get_statut_display(),
                'statut_code': vente.statut,
                'date': vente.created_at,
                'description': vente.get_mode_paiement_display(),
            })

        for facture in FactureModel.objects.filter(client_id=client_id).prefetch_related('lignes'):
            evenements.append({
                'type': 'FACTURE',
                'titre': 'Facture',
                'reference': facture.numero,
                'montant': float(facture.montant_total),
                'statut': facture.get_statut_display(),
                'statut_code': facture.statut,
                'date': facture.created_at,
                'description': facture.type_facture,
            })

        for paiement in Paiement.objects.filter(client_id=client_id):
            entree = paiement.sens == 'ENTREE'
            evenements.append({
                'type': 'PAIEMENT',
                'titre': 'Paiement reçu' if entree else 'Remboursement / sortie',
                'reference': paiement.reference,
                'montant': float(paiement.montant) * (1 if entree else -1),
                'statut': paiement.get_statut_display(),
                'statut_code': paiement.statut,
                'date': paiement.date,
                'description': paiement.get_mode_display(),
            })

        evenements.sort(key=lambda e: e['date'], reverse=True)
        return evenements[:limit] if limit else evenements

    @classmethod
    def get_indicateurs(cls, client_id):
        """Indicateurs commerciaux : valeur du client en un coup d'œil."""
        sejours = Sejour.objects.filter(client_id=client_id).exclude(statut=Sejour.StatutSejour.ANNULE)
        nb_sejours = sejours.count()
        nb_nuits = sum(s.duree_nuits for s in sejours)

        ca_hotel = sum((s.montant_total for s in sejours), Decimal('0'))
        ca_locations = sum(
            (l.montant_total for l in LocationModel.objects.filter(client_id=client_id).exclude(statut='ANNULEE')),
            Decimal('0'),
        )
        ca_pos = sum(
            (v.montant_total for v in Vente.objects.filter(client_id=client_id, statut='PAYEE')),
            Decimal('0'),
        )
        ca_total = ca_hotel + ca_locations + ca_pos

        derniere = sejours.order_by('-date_arrivee').first()
        derniere_visite = derniere.date_arrivee if derniere else None

        prochaine = Reservation.objects.filter(
            client_id=client_id,
            statut__in=[
                Reservation.StatutReservation.CONFIRMEE,
                Reservation.StatutReservation.EN_ATTENTE,
                Reservation.StatutReservation.PARTIELLEMENT_PAYEE,
            ],
            date_arrivee_prevue__gte=timezone.now(),
        ).order_by('date_arrivee_prevue').first()

        nb_annulations = Reservation.objects.filter(
            client_id=client_id,
            statut__in=[Reservation.StatutReservation.ANNULEE, Reservation.StatutReservation.NO_SHOW],
        ).count()

        return {
            'nb_sejours': nb_sejours,
            'nb_nuits': nb_nuits,
            'ca_hotel': ca_hotel,
            'ca_pos': ca_pos,
            'ca_total': ca_total,
            'panier_moyen': (ca_total / nb_sejours) if nb_sejours else Decimal('0'),
            'derniere_visite': derniere_visite,
            'prochaine_reservation': prochaine,
            'nb_annulations': nb_annulations,
        }

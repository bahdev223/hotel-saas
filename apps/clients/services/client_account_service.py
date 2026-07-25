"""Position financière canonique d'un client.

Source de vérité unique pour répondre à « combien ce client doit-il ? »,
utilisée par la fiche client et l'API détail. Tous les calculs restent en
Decimal — la conversion float n'est autorisée qu'au moment de la
sérialisation JSON, jamais dans les totaux métier.
"""
from decimal import Decimal
from django.db.models import Sum

from apps.facturation.models import FactureModel
from apps.paiements.models import Paiement
from apps.comptabilite.models import CompteClient


class ClientAccountService:

    @classmethod
    def get_position(cls, client_id):
        """Retourne la position financière complète du client (Decimal partout).

        - total_facture : somme TTC des factures client émises ou payées
          (les brouillons et annulées ne créent pas de dette).
        - total_paye   : paiements VALIDE en ENTREE rattachés au client.
        - total_rembourse : paiements VALIDE en SORTIE (remboursements/retraits).
        - solde_du     : dette réelle = facturé - payé (jamais négatif ;
          l'excédent devient un acompte disponible).
        - acompte_disponible : trop-perçu utilisable sur de futures factures.
        - solde_comptable : somme des CompteClient tous exercices confondus
          (vision comptable, peut différer de la vision facturation).
        """
        factures = FactureModel.objects.filter(
            client_id=client_id,
            type='CLIENT',
            statut__in=['EMISE', 'PAYEE'],
        ).prefetch_related('lignes')

        total_facture = Decimal('0')
        for facture in factures:
            total_facture += facture.montant_total  # property Decimal (somme des lignes)

        total_paye = Paiement.objects.filter(
            client_id=client_id, statut='VALIDE', sens='ENTREE',
        ).aggregate(t=Sum('montant'))['t'] or Decimal('0')

        total_rembourse = Paiement.objects.filter(
            client_id=client_id, statut='VALIDE', sens='SORTIE',
        ).aggregate(t=Sum('montant'))['t'] or Decimal('0')

        encaissements_nets = total_paye - total_rembourse
        brut = total_facture - encaissements_nets
        solde_du = brut if brut > 0 else Decimal('0')
        acompte_disponible = -brut if brut < 0 else Decimal('0')

        solde_comptable = CompteClient.objects.filter(
            client_id=client_id,
        ).aggregate(t=Sum('solde'))['t'] or Decimal('0')

        return {
            'total_facture': total_facture,
            'total_paye': total_paye,
            'total_rembourse': total_rembourse,
            'solde_du': solde_du,
            'acompte_disponible': acompte_disponible,
            'solde_comptable': solde_comptable,
            'nb_factures': factures.count(),
            'nb_factures_impayees': sum(1 for f in factures if not f.est_payee),
        }

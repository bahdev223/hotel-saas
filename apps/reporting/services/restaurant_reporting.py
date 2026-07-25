from django.db.models import Sum, Count
from apps.pos.models import Vente
from apps.core.models import JourneeExploitation

class RestaurantReportingService:
    @staticmethod
    def get_rapport_journalier(journee_exploitation):
        """
        Calcule les KPIs du restaurant pour une journée d'exploitation donnée.
        """
        ventes = Vente.objects.filter(
            journee_exploitation=journee_exploitation,
            statut__in=['PAYEE', 'PARTIELLEMENT_PAYEE']
        )
        
        ca_net = ventes.aggregate(total=Sum('montant_total'))['total'] or 0
        remises = ventes.aggregate(total=Sum('montant_remise'))['total'] or 0
        marge = ventes.aggregate(total=Sum('marge_totale'))['total'] or 0
        nb_ventes = ventes.count()
        
        return {
            'ca_net': float(ca_net),
            'remises': float(remises),
            'marge_brute': float(marge),
            'nb_ventes': nb_ventes,
            'panier_moyen': float(ca_net) / nb_ventes if nb_ventes > 0 else 0
        }

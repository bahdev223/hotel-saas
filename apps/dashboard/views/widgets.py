from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from datetime import date, timedelta

from apps.pos.models import Vente
from apps.hotel.models import UniteModel
from apps.stock.models import StockEntrepot, Entrepot


@login_required
def widget_data(request, widget_code):
    """API pour récupérer les données d'un widget (AJAX)"""
    today = date.today()

    if widget_code == 'ca_jour':
        ca = Vente.objects.filter(
            statut='PAYEE', created_at__date=today
        ).aggregate(total=Sum('montant_total'))['total'] or 0
        return JsonResponse({'ca': ca})

    elif widget_code == 'occupation':
        toutes = UniteModel.objects.filter(actif=True)
        total = toutes.count()
        occupees = toutes.filter(statut='OCCUPEE').count()
        return JsonResponse({
            'occupees': occupees, 'total': total,
            'taux': round(occupees/total*100, 1) if total > 0 else 0
        })

    elif widget_code == 'commandes_en_cours':
        ventes = Vente.objects.filter(created_at__date=today)
        restaurant = ventes.filter(point_vente__emplacement='RESTAURANT').count()
        bar = ventes.filter(point_vente__emplacement='BAR').count()
        return JsonResponse({'restaurant': restaurant, 'bar': bar, 'room_service': 0, 'total': restaurant + bar})

    elif widget_code == 'ca_7_jours':
        ca_data = []
        for i in range(6, -1, -1):
            jour = today - timedelta(days=i)
            ca = Vente.objects.filter(statut='PAYEE', created_at__date=jour).aggregate(total=Sum('montant_total'))['total'] or 0
            ca_data.append({'date': jour.strftime('%d/%m'), 'ca': ca})
        return JsonResponse({'ca_7_jours': ca_data})

    elif widget_code == 'alertes_stock':
        try:
            bar_entrepot = Entrepot.objects.get(code='BAR')
            alertes_bar = StockEntrepot.objects.filter(entrepot=bar_entrepot, quantite__lte=0).count()
        except Entrepot.DoesNotExist:
            alertes_bar = 0
        return JsonResponse({'bar': alertes_bar, 'total': alertes_bar})

    return JsonResponse({'error': 'Widget non trouvé'}, status=404)


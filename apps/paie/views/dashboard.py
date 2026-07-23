from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from ..models import PeriodePaie, BulletinPaie


@login_required
def dashboard(request):
    """ Dashboard paie """
    periode_courante = PeriodePaie.objects.filter(cloture=False).first()
    
    stats = {
        'total_bulletins': BulletinPaie.objects.count(),
        'total_net': BulletinPaie.objects.aggregate(total=Sum('net_a_payer'))['total'] or 0,
        'bulletins_mois': 0,
        'net_mois': 0,
    }
    
    if periode_courante:
        bulletins_mois = BulletinPaie.objects.filter(periode=periode_courante)
        stats['bulletins_mois'] = bulletins_mois.count()
        stats['net_mois'] = bulletins_mois.aggregate(total=Sum('net_a_payer'))['total'] or 0
    
    context = {
        'stats': stats,
        'periode_courante': periode_courante,
    }
    return render(request, 'paie/dashboard.html', context)

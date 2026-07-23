# apps/tresorerie/views/dashboard.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Sum
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal

from ..models import Caisse, MouvementCaisse
from apps.comptabilite.models import CompteModel


@login_required
def dashboard_tresorier(request):
    """Dashboard unique trésorerie - Tout en un"""
    
    today = timezone.now().date()
    today_start = datetime.combine(today, datetime.min.time())
    
    # ========== CAISSES ==========
    toutes_caisses = Caisse.objects.all().order_by('code')
    caisses_physiques = [c for c in toutes_caisses if c.actif]
    caisse_centrale = Caisse.objects.filter(type_financier='ESPECES', role='CENTRALE', actif=True).first()
    
    solde_total = sum(c.solde for c in toutes_caisses if c.actif and c.type_financier != 'BANQUE')
    solde_especes = sum(c.solde for c in toutes_caisses if c.type_financier == 'ESPECES' and c.actif)
    solde_mobile = sum(c.solde for c in toutes_caisses if c.type_financier == 'MOBILE_MONEY' and c.actif)
    solde_banque = sum(c.solde for c in toutes_caisses if c.type_financier == 'BANQUE' and c.actif)
    
    # ========== MOUVEMENTS AVEC FILTRES DATE + CAISSE + TYPE + PAGINATION ==========
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    filtre_caisse = request.GET.get('caisse', '')
    filtre_type_mvt = request.GET.get('type_mvt', '')

    mouvements_qs = MouvementCaisse.objects.select_related('caisse')

    if date_from:
        try:
            dt_from = datetime.strptime(date_from, '%Y-%m-%d')
            mouvements_qs = mouvements_qs.filter(date__gte=dt_from)
        except ValueError:
            pass
    if date_to:
        try:
            dt_to = datetime.strptime(date_to, '%Y-%m-%d') + timedelta(days=1)
            mouvements_qs = mouvements_qs.filter(date__lt=dt_to)
        except ValueError:
            pass
    if filtre_caisse:
        mouvements_qs = mouvements_qs.filter(caisse_id=filtre_caisse)
    if filtre_type_mvt:
        mouvements_qs = mouvements_qs.filter(type_mouvement=filtre_type_mvt)

    mouvements_qs = mouvements_qs.order_by('-date')
    paginator = Paginator(mouvements_qs, 50)
    page_number = request.GET.get('page', 1)
    mouvements_page = paginator.get_page(page_number)
    
    # Flux récents (24h)
    flux_recents = MouvementCaisse.objects.filter(
        date__gte=today_start - timedelta(days=1)
    ).select_related('caisse', 'created_by').order_by('-date')[:20]
    flux_list = []
    for flux in flux_recents:
        flux_list.append({
            'heure': flux.date.strftime('%H:%M'),
            'type': flux.type_mouvement,
            'montant': float(flux.montant),
            'libelle': flux.libelle,
            'caisse': flux.caisse.nom,
        })
    
    # Encaissements/décaissements du jour (hors banques)
    base_flux = MouvementCaisse.objects.filter(date__date=today).exclude(caisse__type_financier='BANQUE')
    encaissements_jour = base_flux.filter(type_mouvement='ENTREE').aggregate(total=Sum('montant'))['total'] or Decimal(0)
    decaissements_jour = base_flux.filter(type_mouvement='SORTIE').aggregate(total=Sum('montant'))['total'] or Decimal(0)
    flux_net_jour = encaissements_jour - decaissements_jour
    
    context = {
        'solde_total': float(solde_total),
        'solde_especes': float(solde_especes),
        'solde_mobile': float(solde_mobile),
        'solde_banque': float(solde_banque),
        'encaissements_jour': float(encaissements_jour),
        'decaissements_jour': float(decaissements_jour),
        'flux_net_jour': float(flux_net_jour),
        'toutes_caisses': toutes_caisses,
        'caisses_physiques': caisses_physiques,
        'caisse_centrale_id': caisse_centrale.id if caisse_centrale else None,

        'mouvements': mouvements_page,
        'page_obj': mouvements_page,
        'date_from': date_from,
        'date_to': date_to,
        'flux_recents': flux_list,
        'alertes': [],
        'today': today,
        'today_str': today.strftime('%d/%m/%Y'),
        'est_bloque_tresorerie': False,
    }
    return render(request, 'tresorerie/dashboard.html', context)


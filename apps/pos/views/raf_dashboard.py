from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Count
from datetime import timedelta
from django.http import JsonResponse

from ..models import PointVente, SessionCaisse, ShiftEmploye, Vente
from apps.tresorerie.models import TransfertCaisse
from apps.pos.services.raf_caisse_service import RafCaisseService
from apps.authentication.groups import PATRON, MANAGER, RAF


def _is_raf(user):
    return user.is_superuser or any(
        g in [PATRON, MANAGER, RAF]
        for g in user.groups.values_list('name', flat=True)
    )


def _get_context_data():
    today = timezone.now().date()
    now = timezone.now()

    sessions_ouvertes = SessionCaisse.objects.filter(statut='OUVERTE').select_related('point_vente', 'ouverte_par').order_by('-date_ouverture')
    sessions_attente = SessionCaisse.objects.filter(statut='FERMEE').select_related('point_vente', 'ouverte_par', 'fermee_par').order_by('-date_fermeture')
    sessions_validees_ajd = SessionCaisse.objects.filter(
        statut='VALIDEE', date_fermeture__date=today
    ).select_related('point_vente', 'validee_par').order_by('-date_fermeture')
    transferts_ajd = TransfertCaisse.objects.filter(date__date=today).select_related('source', 'destination', 'valide_par').order_by('-date')
    shifts_ajd = ShiftEmploye.objects.filter(debut_prevu__date=today).exclude(statut='ANNULE').select_related('affectation__point_vente', 'affectation__employe').order_by('debut_prevu')
    demandes = RafCaisseService.get_demandes_ouverture()

    stats = {
        'nb_ouvertes': sessions_ouvertes.count(),
        'nb_aujourdhui': SessionCaisse.objects.filter(date_ouverture__date=today).count(),
        'nb_attente': sessions_attente.count(),
        'nb_validees_ajd': sessions_validees_ajd.count(),
        'montant_transfere_ajd': float(transferts_ajd.filter(source__role='POINT_VENTE').aggregate(total=Sum('montant'))['total'] or 0),
        'nb_plannings_ajd': shifts_ajd.count(),
        'nb_pv_actifs': PointVente.objects.filter(actif=True).count(),
        'total_a_traiter': sessions_ouvertes.count() + sessions_attente.count(),
        'ca_aujourdhui': float(Vente.objects.filter(created_at__date=today, statut='PAYEE').aggregate(total=Sum('montant_total'))['total'] or 0),
    }

    return {
        'stats': stats, 'sessions_ouvertes': sessions_ouvertes,
        'sessions_attente': sessions_attente,
        'sessions_validees_ajd': sessions_validees_ajd,
        'transferts_ajd': transferts_ajd, 'plannings_ajd': shifts_ajd,
        'demandes': demandes, 'today': today, 'now': now,
    }


@login_required
def raf_dashboard(request):
    if not _is_raf(request.user):
        messages.error(request, "Acc\u00e8s interdit.")
        return redirect('dashboard:index')
    ctx = _get_context_data()
    return render(request, 'pos/raf/dashboard.html', ctx)


@login_required
def raf_dashboard_data_api(request):
    if not _is_raf(request.user):
        return JsonResponse({'success': False, 'error': 'Acc\u00e8s interdit'}, status=403)

    today = timezone.now().date()
    now = timezone.now()

    sessions_ouvertes = SessionCaisse.objects.filter(statut='OUVERTE')
    sessions_auj = SessionCaisse.objects.filter(date_ouverture__date=today)
    sessions_attente = SessionCaisse.objects.filter(statut='FERMEE')
    sessions_validees_ajd = SessionCaisse.objects.filter(statut='VALIDEE', date_fermeture__date=today)
    transferts_ajd = TransfertCaisse.objects.filter(date__date=today)
    shifts_ajd = ShiftEmploye.objects.filter(debut_prevu__date=today).exclude(statut='ANNULE')

    stats = {
        'nb_ouvertes': sessions_ouvertes.count(),
        'nb_aujourdhui': sessions_auj.count(),
        'nb_attente': sessions_attente.count(),
        'nb_validees_ajd': sessions_validees_ajd.count(),
        'montant_transfere_ajd': float(transferts_ajd.filter(source__role='POINT_VENTE').aggregate(total=Sum('montant'))['total'] or 0),
        'nb_plannings_ajd': shifts_ajd.count(),
        'nb_pv_actifs': PointVente.objects.filter(actif=True).count(),
        'total_a_traiter': sessions_ouvertes.count() + sessions_attente.count(),
        'ca_aujourdhui': float(Vente.objects.filter(created_at__date=today, statut='PAYEE').aggregate(total=Sum('montant_total'))['total'] or 0),
    }

    ouvertes_data = []
    for s in sessions_ouvertes.select_related('point_vente', 'ouverte_par').order_by('-date_ouverture'):
        ouvertes_data.append({
            'id': s.id, 'point_vente': s.point_vente.nom if s.point_vente else 'N/A',
            'caissier': s.ouverte_par.nom_complet if s.ouverte_par else 'N/A',
            'date_ouverture': s.date_ouverture.strftime('%d/%m/%Y %H:%M'),
            'duree': s.date_ouverture.strftime('%H:%M') if s.date_ouverture else '-',
            'nb_ventes': s.nombre_ventes, 'total_ventes': float(s.total_ventes),
            'timesince': s.date_ouverture.strftime('%Hh%M') if s.date_ouverture else '-',
            'solde_initial': float(s.solde_initial),
        })

    attente_data = []
    for s in sessions_attente.select_related('point_vente', 'ouverte_par', 'fermee_par').order_by('-date_fermeture'):
        attente_data.append({
            'id': s.id, 'point_vente': s.point_vente.nom if s.point_vente else 'N/A',
            'caissier': s.ouverte_par.nom_complet if s.ouverte_par else 'N/A',
            'ferme_par': s.fermee_par.nom_complet if s.fermee_par else 'N/A',
            'ferme_le': s.date_fermeture.strftime('%d/%m/%Y %H:%M') if s.date_fermeture else 'N/A',
            'nb_ventes': s.nombre_ventes, 'total_ventes': float(s.total_ventes),
        })

    validees_data = []
    for s in sessions_validees_ajd.select_related('point_vente', 'validee_par').order_by('-date_fermeture'):
        comptage = getattr(s, 'comptage', None)
        validees_data.append({
            'id': s.id, 'point_vente': s.point_vente.nom if s.point_vente else 'N/A',
            'raf': s.validee_par.nom_complet if s.validee_par else 'N/A',
            'date_collecte': s.date_fermeture.strftime('%H:%M') if s.date_fermeture else 'N/A',
            'montant': float(comptage.especes_comptees) if comptage else 0,
        })

    transferts_data = []
    for t in transferts_ajd.select_related('source', 'destination', 'valide_par').order_by('-date'):
        transferts_data.append({
            'reference': t.reference or '-', 'heure': t.date.strftime('%H:%M') if t.date else '-',
            'source': t.source.nom, 'destination': t.destination.nom,
            'montant': float(t.montant),
            'valide_par': t.valide_par.get_full_name() if t.valide_par else '-',
        })

    plannings_data = []
    for p in shifts_ajd.select_related('affectation__point_vente', 'affectation__employe').order_by('debut_prevu'):
        pv = p.affectation.point_vente if p.affectation else None
        emp = p.affectation.employe if p.affectation else None
        plannings_data.append({
            'id': p.id, 'point_vente': pv.nom if pv else '',
            'employe': emp.nom_complet if emp else '',
            'horaire': f"{p.debut_prevu.strftime('%H:%M')} - {p.fin_prevue.strftime('%H:%M')}",
            'statut': p.statut, 'statut_display': p.get_statut_display(),
        })

    demandes_data = []
    for d in RafCaisseService.get_demandes_ouverture():
        demandes_data.append({
            'point_vente_id': d['point_vente'].id, 'caisse_id': d['caisse'].id,
            'planning_id': d['planning'].id,
            'point_vente': d['point_vente'].nom,
            'employe': d['employe'].nom_complet,
            'planning': f"{d['planning'].debut_prevu.strftime('%H:%M')} - {d['planning'].fin_prevue.strftime('%H:%M')}",
            'solde_actuel': d['solde_actuel'],
        })

    return JsonResponse({
        'success': True, 'stats': stats, 'ouvertes': ouvertes_data,
        'attente': attente_data, 'validees': validees_data,
        'transferts': transferts_data, 'plannings': plannings_data,
        'demandes': demandes_data,
        'now': now.strftime('%H:%M:%S'), 'date': today.strftime('%d/%m/%Y'),
    })

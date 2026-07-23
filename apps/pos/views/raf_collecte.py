from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Sum, Q
from decimal import Decimal
from ..models import SessionCaisse, PointVente, SessionPlanning
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse, TransfertCaisse
from ..services.raf_caisse_service import RafCaisseService
from apps.authentication.groups import PATRON, MANAGER, RAF


def _is_raf(user):
    return user.is_superuser or any(
        g in [PATRON, MANAGER, RAF]
        for g in user.groups.values_list('name', flat=True)
    )


@login_required
def raf_collecte(request):
    """Page principale de collecte des caisses avec onglets"""
    if not _is_raf(request.user):
        messages.error(request, "Accès interdit.")
        return redirect('dashboard:index')

    sessions_ouvertes = RafCaisseService.get_sessions_pour_collecte()
    sessions_attente = RafCaisseService.get_sessions_en_attente()
    collectees = RafCaisseService.get_collectees()
    demandes_ouverture = RafCaisseService.get_demandes_ouverture()

    today = timezone.now().date()
    stats = {
        'nb_ouvertes': len(sessions_ouvertes),
        'nb_attente': len(sessions_attente),
        'nb_collectees_ajd': SessionCaisse.objects.filter(
            date_collecte__date=today, fonds_collectes=True
        ).count(),
        'montant_transfere_ajd': TransfertCaisse.objects.filter(
            date__date=today, source__role='POINT_VENTE'
        ).aggregate(total=Sum('montant'))['total'] or 0,
        'nb_demandes': len(demandes_ouverture),
    }

    context = {
        'sessions_ouvertes': sessions_ouvertes,
        'sessions_attente': sessions_attente,
        'collectees': collectees,
        'demandes_ouverture': demandes_ouverture,
        'stats': stats,
        'today': today,
    }
    return render(request, 'pos/raf/collecte.html', context)


@login_required
def raf_transferts(request):
    """Historique des transferts RAF"""
    if not _is_raf(request.user):
        messages.error(request, "Accès interdit.")
        return redirect('dashboard:index')

    transferts = TransfertCaisse.objects.filter(
        Q(source__role='POINT_VENTE') | Q(destination__role='POINT_VENTE')
    ).select_related('source', 'destination', 'valide_par').order_by('-date')[:100]

    today = timezone.now().date()
    stats = {
        'nb_ajd': transferts.filter(date__date=today).count(),
        'total_ajd': transferts.filter(date__date=today).aggregate(total=Sum('montant'))['total'] or 0,
    }

    context = {'transferts': transferts, 'stats': stats, 'today': today}
    return render(request, 'pos/raf/transferts.html', context)


from django.http import JsonResponse

@login_required
def raf_liste_collecte_api(request):
    if not _is_raf(request.user):
        return JsonResponse({'success': False, 'error': 'Accès interdit'}, status=403)

    data = {'ouvertes': [], 'attente': [], 'collectees': []}

    for s in RafCaisseService.get_sessions_pour_collecte():
        ses = s['session']
        data['ouvertes'].append({
            'id': ses.id, 'point_vente': ses.point_vente.nom if ses.point_vente else 'N/A',
            'point_vente_id': ses.point_vente_id, 'caisse_id': ses.caisse_id,
            'caissier': ses.caissier_ouverture.nom_complet if ses.caissier_ouverture else 'N/A',
            'date_ouverture': ses.date_ouverture.strftime('%d/%m/%Y %H:%M'),
            'solde_initial': float(ses.solde_initial), 'total_ventes': s['total_ventes'],
            'nb_ventes': s['nb_ventes'], 'total_especes': s['total_especes'],
            'solde_attendu': s['solde_attendu'],
        })

    for s in RafCaisseService.get_sessions_en_attente():
        ses = s['session']
        data['attente'].append({
            'id': ses.id, 'point_vente': ses.point_vente.nom if ses.point_vente else 'N/A',
            'caissier': ses.caissier_ouverture.nom_complet if ses.caissier_ouverture else 'N/A',
            'ferme_par': s['ferme_par'], 'ferme_le': s['ferme_le'],
            'solde_initial': float(ses.solde_initial), 'total_ventes': s['total_ventes'],
            'nb_ventes': s['nb_ventes'], 'total_especes': s['total_especes'],
            'solde_attendu': s['solde_attendu'],
        })

    for s in RafCaisseService.get_collectees():
        ses = s['session']
        data['collectees'].append({
            'id': ses.id, 'point_vente': ses.point_vente.nom if ses.point_vente else 'N/A',
            'collecte_par': s['collecte_par'], 'collecte_le': s['collecte_le'],
            'montant': s['montant_transfere'], 'reference': s['reference_transfert'],
        })

    return JsonResponse({'success': True, **data})


@login_required
def raf_ouvrir_depot_api(request):
    if not _is_raf(request.user):
        return JsonResponse({'success': False, 'error': 'Accès interdit'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    import json
    try:
        data = json.loads(request.body)
        pv_id, caisse_id, montant = data.get('point_vente_id'), data.get('caisse_id'), data.get('montant_depot')
        planning_id = data.get('planning_id')
        if not all([pv_id, caisse_id, montant]):
            return JsonResponse({'success': False, 'error': 'Paramètres manquants'})
        employe = getattr(request.user, 'employe', None)
        if not employe:
            return JsonResponse({'success': False, 'error': 'Profil employé requis'})
        pv = PointVente.objects.get(id=pv_id)
        caisse = Caisse.objects.get(id=caisse_id)
        planning = SessionPlanning.objects.get(id=planning_id) if planning_id else None
        resultat = RafCaisseService.ouvrir_avec_depot(pv, caisse, employe, planning, employe, montant)
        return JsonResponse({'success': True, 'session_id': resultat.id, 'solde_initial': float(resultat.solde_initial)})
    except PointVente.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Point de vente introuvable'})
    except Caisse.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Caisse introuvable'})
    except SessionPlanning.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Planning introuvable'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erreur: {str(e)}'})


@login_required
def raf_declarer_solde_initial_api(request):
    """API: RAF déclare/modifie solde initial d'une session déjà ouverte"""
    if not _is_raf(request.user):
        return JsonResponse({'success': False, 'error': 'Accès interdit'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    import json
    try:
        data = json.loads(request.body)
        session_id, nouveau_solde = data.get('session_id'), data.get('solde_initial')
        if not session_id or nouveau_solde is None:
            return JsonResponse({'success': False, 'error': 'Paramètres manquants'})
        employe = getattr(request.user, 'employe', None)
        if not employe:
            return JsonResponse({'success': False, 'error': 'Profil employé requis'})
        session = SessionCaisse.objects.get(id=session_id)
        if session.statut != 'OUVERTE':
            return JsonResponse({'success': False, 'error': 'La session doit être ouverte'})
        resultat = RafCaisseService.declarer_solde_initial(session, employe, nouveau_solde)
        return JsonResponse({'success': True, 'solde_initial': float(resultat.solde_initial)})
    except SessionCaisse.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session introuvable'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erreur: {str(e)}'})


@login_required
def raf_collecter_api(request):
    """API: RAF collecte une session (fermée → collecte différée, ou ouverte → directe)"""
    if not _is_raf(request.user):
        return JsonResponse({'success': False, 'error': 'Accès interdit'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)

    import json
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        solde_reel = data.get('solde_reel')
        montant_transfert = data.get('montant_transfert', 0)
        notes = data.get('notes', '')

        if not all([session_id, solde_reel is not None]):
            return JsonResponse({'success': False, 'error': 'Paramètres manquants'})

        employe = getattr(request.user, 'employe', None)
        if not employe:
            return JsonResponse({'success': False, 'error': 'Profil employé requis'})

        session = SessionCaisse.objects.get(id=session_id)

        if session.statut == 'FERMEE':
            resultat = RafCaisseService.collecter_session_fermee(session, employe, solde_reel, montant_transfert, notes)
        elif session.statut == 'OUVERTE':
            resultat = RafCaisseService.collecter_et_fermer(session, employe, solde_reel, montant_transfert, notes)
        else:
            return JsonResponse({'success': False, 'error': f"Statut session invalide: {session.statut}"})

        return JsonResponse({
            'success': True,
            'session_id': resultat['session'].id,
            'solde_attendu': float(resultat['solde_attendu']),
            'solde_reel': float(resultat['solde_reel']),
            'depot': float(resultat['depot']),
            'solde_restant': float(resultat['solde_restant']),
            'difference': float(resultat['difference']),
            'transfert_id': resultat['transfert'].id if resultat['transfert'] else None,
        })

    except SessionCaisse.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Session introuvable'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'Erreur: {str(e)}'})

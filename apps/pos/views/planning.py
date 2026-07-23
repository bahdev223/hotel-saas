# apps/pos/views/planning.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, timedelta, date, time
import json

from django.db.models import Q

from ..models import PointVente, SessionPlanning
from apps.rh.models import Employe


def _intervalle_planning(p_date, h_debut, h_fin):
    """Convertit un créneau en [debut_dt, fin_dt) — gère les créneaux de nuit.
    h_fin <= h_debut signifie que le créneau passe minuit (ou dure 24h si égal)."""
    debut = datetime.combine(p_date, h_debut)
    if h_fin == h_debut:
        fin = debut + timedelta(days=1)
    elif h_fin < h_debut:
        fin = datetime.combine(p_date + timedelta(days=1), h_fin)
    else:
        fin = datetime.combine(p_date, h_fin)
    return debut, fin


def _conflits_planning(employe, point_vente, p_date, h_debut, h_fin, exclude_id=None):
    """Plannings en conflit avec le créneau demandé :
    - même employé, quel que soit le PV (il ne peut pas être à deux endroits) ;
    - même PV, quel que soit l'employé (une caisse = un caissier à la fois).
    Fenêtre veille/jour/lendemain pour couvrir les créneaux de nuit."""
    debut, fin = _intervalle_planning(p_date, h_debut, h_fin)
    qs = SessionPlanning.objects.filter(
        date__in=[p_date - timedelta(days=1), p_date, p_date + timedelta(days=1)],
    ).exclude(statut='ANNULE').filter(
        Q(employe=employe) | Q(point_vente=point_vente)
    ).select_related('employe', 'point_vente')
    if exclude_id:
        qs = qs.exclude(id=exclude_id)

    conflits = []
    for p in qs:
        p_debut, p_fin = _intervalle_planning(p.date, p.heure_debut, p.heure_fin)
        if debut < p_fin and p_debut < fin:
            conflits.append(p)
    return conflits


def _message_conflits(conflits):
    details = "; ".join(
        f"{p.employe.nom_complet} sur {p.point_vente.nom} le {p.date.strftime('%d/%m')} "
        f"{p.heure_debut.strftime('%H:%M')}-{p.heure_fin.strftime('%H:%M')}"
        for p in conflits[:3]
    )
    return f"Conflit de planning — créneau déjà occupé : {details}"


@login_required
def planning_view(request):
    """Page de planning hebdomadaire des sessions"""
    points = PointVente.objects.filter(actif=True)
    employes = Employe.objects.filter(actif=True).order_by('nom', 'prenom')
    context = {
        'points': points,
        'employes': employes,
    }
    return render(request, 'pos/planning.html', context)


@login_required
def api_planning_liste(request):
    """API: retourne les sessions planifiées sur une période"""
    date_debut = request.GET.get('debut')
    date_fin = request.GET.get('fin')
    point_vente_id = request.GET.get('point_vente')
    employe_id = request.GET.get('employe')

    plannings = SessionPlanning.objects.all().select_related('employe', 'point_vente')

    if date_debut:
        plannings = plannings.filter(date__gte=date_debut)
    if date_fin:
        plannings = plannings.filter(date__lte=date_fin)
    if point_vente_id:
        plannings = plannings.filter(point_vente_id=point_vente_id)
    if employe_id:
        plannings = plannings.filter(employe_id=employe_id)

    data = []
    for p in plannings:
        session = None
        if p.statut == 'EFFECTUE':
            from ..models import SessionCaisse
            session = SessionCaisse.objects.filter(
                point_vente=p.point_vente,
                caissier_ouverture=p.employe,
                date_ouverture__date=p.date
            ).first()
        data.append({
            'id': p.id,
            'point_vente_id': p.point_vente_id,
            'point_vente': p.point_vente.nom,
            'employe_id': p.employe_id,
            'employe': p.employe.nom_complet,
            'date': p.date.strftime('%Y-%m-%d'),
            'heure_debut': p.heure_debut.strftime('%H:%M'),
            'heure_fin': p.heure_fin.strftime('%H:%M'),
            'statut': p.statut,
            'notes': p.notes or '',
            'session_id': session.id if session else None,
        })

    return JsonResponse({'success': True, 'plannings': data})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_planning_creer(request):
    """API: crée ou modifie une session planifiée"""
    try:
        data = json.loads(request.body)
        planning_id = data.get('id')

        point_vente = get_object_or_404(PointVente, id=data['point_vente_id'])
        employe = get_object_or_404(Employe, id=data['employe_id'])

        p_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        h_debut = datetime.strptime(data['heure_debut'], '%H:%M').time()
        h_fin = datetime.strptime(data['heure_fin'], '%H:%M').time()

        # Verrou : aucun chevauchement (même employé ou même PV)
        conflits = _conflits_planning(employe, point_vente, p_date, h_debut, h_fin,
                                      exclude_id=planning_id)
        if conflits:
            return JsonResponse({'success': False, 'error': _message_conflits(conflits)})

        if planning_id:
            planning = get_object_or_404(SessionPlanning, id=planning_id)
            planning.point_vente = point_vente
            planning.employe = employe
            planning.date = p_date
            planning.heure_debut = h_debut
            planning.heure_fin = h_fin
            planning.statut = data.get('statut', 'PLANIFIE')
            planning.notes = data.get('notes', '')
            planning.save()
            msg = 'Planning mis à jour'
        else:
            planning = SessionPlanning.objects.create(
                point_vente=point_vente,
                employe=employe,
                date=p_date,
                heure_debut=h_debut,
                heure_fin=h_fin,
                statut=data.get('statut', 'PLANIFIE'),
                notes=data.get('notes', ''),
            )
            msg = 'Session planifiée'

        return JsonResponse({
            'success': True,
            'message': msg,
            'planning': {
                'id': planning.id,
                'point_vente_id': planning.point_vente_id,
                'point_vente': planning.point_vente.nom,
                'employe_id': planning.employe_id,
                'employe': planning.employe.nom_complet,
                'date': planning.date.strftime('%Y-%m-%d'),
                'heure_debut': planning.heure_debut.strftime('%H:%M'),
                'heure_fin': planning.heure_fin.strftime('%H:%M'),
                'statut': planning.statut,
                'notes': planning.notes or '',
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_planning_supprimer(request):
    """API: supprime une session planifiée"""
    try:
        data = json.loads(request.body)
        planning = get_object_or_404(SessionPlanning, id=data['id'])
        planning.delete()
        return JsonResponse({'success': True, 'message': 'Planning supprimé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_planning_creer_masse(request):
    """API: crée plusieurs sessions planifiées en une fois + détection conflits"""
    try:
        data = json.loads(request.body)
        employe_id = data.get('employe_id')
        point_vente_id = data.get('point_vente_id')
        date_debut = datetime.strptime(data['date_debut'], '%Y-%m-%d').date()
        date_fin = datetime.strptime(data['date_fin'], '%Y-%m-%d').date()
        heure_debut = datetime.strptime(data['heure_debut'], '%H:%M').time()
        heure_fin = datetime.strptime(data['heure_fin'], '%H:%M').time()
        jours_semaine = data.get('jours_semaine', [1,2,3,4,5,6,7])  # 1=Lun...7=Dim
        statut = data.get('statut', 'PLANIFIE')
        notes = data.get('notes', '')

        employe = get_object_or_404(Employe, id=employe_id)
        point_vente = get_object_or_404(PointVente, id=point_vente_id)

        if date_debut > date_fin:
            return JsonResponse({'success': False, 'error': 'La date de début doit être avant la date de fin'})

        # Carte jour semaine: 0=Lun...6=Dim
        jour_map = {1:0,2:1,3:2,4:3,5:4,6:5,7:6}
        jours_filtre = [jour_map.get(j, j) for j in jours_semaine]

        created = []
        conflits = []

        current = date_debut
        while current <= date_fin:
            jour_sem = current.weekday()  # 0=Lun
            if jour_sem in jours_filtre:
                # Verrou : aucun chevauchement (même employé sur un autre PV,
                # ou un autre employé sur le même PV)
                conflits_jour = _conflits_planning(employe, point_vente, current, heure_debut, heure_fin)
                if conflits_jour:
                    conflit = conflits_jour[0]
                    conflits.append({
                        'date': current.strftime('%Y-%m-%d'),
                        'existant_id': conflit.id,
                        'existant_heure': f"{conflit.heure_debut.strftime('%H:%M')}-{conflit.heure_fin.strftime('%H:%M')}",
                        'point_vente': conflit.point_vente.nom,
                        'employe': conflit.employe.nom_complet,
                    })
                else:
                    planning = SessionPlanning.objects.create(
                        point_vente=point_vente,
                        employe=employe,
                        date=current,
                        heure_debut=heure_debut,
                        heure_fin=heure_fin,
                        statut=statut,
                        notes=notes,
                    )
                    created.append({
                        'id': planning.id,
                        'date': planning.date.strftime('%Y-%m-%d'),
                        'heure_debut': planning.heure_debut.strftime('%H:%M'),
                        'heure_fin': planning.heure_fin.strftime('%H:%M'),
                        'statut': planning.statut,
                    })
            current += timedelta(days=1)

        return JsonResponse({
            'success': True,
            'message': f"{len(created)} planning(s) créé(s)",
            'created': created,
            'conflits': conflits,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# Legacy employee scheduling (pointage)
@login_required
def api_planning_employes(request):
    """API: retourne les employés d'un point de vente avec leur horaire du jour"""
    point_id = request.GET.get('point_vente')
    if not point_id:
        return JsonResponse({'success': False, 'error': 'point_vente requis'})

    employes = Employe.objects.filter(
        point_vente_id=point_id, actif=True
    ).order_by('nom')

    from apps.rh.models import Pointage
    today = timezone.now().date()
    data = []
    for e in employes:
        pointage = Pointage.objects.filter(
            employe=e, date_pointage=today
        ).first()
        data.append({
            'id': e.id,
            'matricule': e.matricule,
            'nom': f"{e.nom} {e.prenom}",
            'poste': str(e.poste) if e.poste else '',
            'pointage_id': pointage.id_pointage if pointage else None,
            'heure_entree': str(pointage.heure_entree)[:5] if pointage and pointage.heure_entree else '',
            'heure_sortie': str(pointage.heure_sortie)[:5] if pointage and pointage.heure_sortie else '',
        })

    return JsonResponse({'success': True, 'employes': data})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_set_horaire(request):
    """API: définit l'horaire d'un employé pour aujourd'hui"""
    try:
        data = json.loads(request.body)
        employe_id = data.get('employe_id')
        heure_entree = data.get('heure_entree', '')
        heure_sortie = data.get('heure_sortie', '')

        employe = Employe.objects.get(id=employe_id, actif=True)
        from apps.rh.models import Pointage
        today = timezone.now().date()

        pointage, created = Pointage.objects.get_or_create(
            employe=employe,
            date_pointage=today,
            defaults={'id_pointage': f"PTG{today.strftime('%y%m%d')}{employe.matricule}"}
        )

        if heure_entree:
            pointage.heure_entree = datetime.strptime(heure_entree, '%H:%M').time()
        else:
            pointage.heure_entree = None

        if heure_sortie:
            pointage.heure_sortie = datetime.strptime(heure_sortie, '%H:%M').time()
        else:
            pointage.heure_sortie = None

        pointage.save()

        return JsonResponse({
            'success': True,
            'message': f'Horaire mis à jour pour {employe.nom} {employe.prenom}'
        })

    except Employe.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employé introuvable'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

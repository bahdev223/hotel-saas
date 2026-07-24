from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
from datetime import datetime, timedelta, date, time
import json

from django.db.models import Q

from ..models import PointVente, ShiftEmploye, AffectationPointVente
from apps.rh.models import Employe


def _intervalle_planning(debut_dt, fin_dt):
    return debut_dt, fin_dt


def _conflits_planning(affectation, debut_prevu, fin_prevue, exclude_id=None):
    qs = ShiftEmploye.objects.filter(
        affectation=affectation,
    ).exclude(statut='ANNULE').filter(
        Q(debut_prevu__lt=fin_prevue) & Q(fin_prevue__gt=debut_prevu)
    )
    if exclude_id:
        qs = qs.exclude(id=exclude_id)
    return list(qs)


def _message_conflits(conflits):
    details = "; ".join(
        f"{s.affectation.employe.nom_complet if s.affectation else '?'} "
        f"sur {s.affectation.point_vente.nom if s.affectation and s.affectation.point_vente else '?'} "
        f"le {s.debut_prevu.strftime('%d/%m %H:%M')}-{s.fin_prevue.strftime('%H:%M')}"
        for s in conflits[:3]
    )
    return f"Conflit de planning \u2014 cr\u00e9neau d\u00e9j\u00e0 occup\u00e9 : {details}"


@login_required
def planning_view(request):
    points = PointVente.objects.filter(actif=True)
    employes = Employe.objects.filter(actif=True).order_by('nom', 'prenom')
    context = {'points': points, 'employes': employes}
    return render(request, 'pos/planning.html', context)


@login_required
def api_planning_liste(request):
    date_debut = request.GET.get('debut')
    date_fin = request.GET.get('fin')
    point_vente_id = request.GET.get('point_vente')
    employe_id = request.GET.get('employe')

    shifts = ShiftEmploye.objects.all().select_related('affectation__point_vente', 'affectation__employe')

    if date_debut:
        shifts = shifts.filter(debut_prevu__date__gte=date_debut)
    if date_fin:
        shifts = shifts.filter(debut_prevu__date__lte=date_fin)
    if point_vente_id:
        shifts = shifts.filter(affectation__point_vente_id=point_vente_id)
    if employe_id:
        shifts = shifts.filter(affectation__employe_id=employe_id)

    data = []
    for s in shifts:
        pv = s.affectation.point_vente if s.affectation else None
        emp = s.affectation.employe if s.affectation else None
        session = None
        try:
            session = s.sessions.first()
        except Exception:
            pass
        data.append({
            'id': s.id,
            'point_vente_id': pv.id if pv else None,
            'point_vente': pv.nom if pv else '',
            'employe_id': emp.id if emp else None,
            'employe': emp.nom_complet if emp else '',
            'date': s.debut_prevu.strftime('%Y-%m-%d'),
            'heure_debut': s.debut_prevu.strftime('%H:%M'),
            'heure_fin': s.fin_prevue.strftime('%H:%M'),
            'statut': s.statut,
            'notes': s.notes or '',
            'session_id': session.id if session else None,
        })

    return JsonResponse({'success': True, 'plannings': data})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_planning_creer(request):
    try:
        data = json.loads(request.body)
        shift_id = data.get('id')

        point_vente = get_object_or_404(PointVente, id=data['point_vente_id'])
        employe = get_object_or_404(Employe, id=data['employe_id'])

        affectation, _ = AffectationPointVente.objects.get_or_create(
            employe=employe, point_vente=point_vente,
            defaults={'role': 'CAISSIER', 'actif': True, 'peut_vendre': True, 'peut_encaisser': True},
        )

        p_date = datetime.strptime(data['date'], '%Y-%m-%d').date()
        h_debut = datetime.strptime(data['heure_debut'], '%H:%M').time()
        h_fin = datetime.strptime(data['heure_fin'], '%H:%M').time()
        debut_dt = timezone.make_aware(datetime.combine(p_date, h_debut))
        fin_dt = timezone.make_aware(datetime.combine(p_date, h_fin))
        if fin_dt <= debut_dt:
            fin_dt += timedelta(days=1)

        conflits = _conflits_planning(affectation, debut_dt, fin_dt, exclude_id=shift_id)
        if conflits:
            return JsonResponse({'success': False, 'error': _message_conflits(conflits)})

        statut = data.get('statut', 'PLANIFIE')

        if shift_id:
            shift = get_object_or_404(ShiftEmploye, id=shift_id)
            shift.debut_prevu = debut_dt
            shift.fin_prevue = fin_dt
            shift.statut = statut
            shift.notes = data.get('notes', '')
            shift.save()
            msg = 'Planning mis \u00e0 jour'
        else:
            shift = ShiftEmploye.objects.create(
                affectation=affectation,
                debut_prevu=debut_dt, fin_prevue=fin_dt,
                statut=statut, notes=data.get('notes', ''),
                cree_par=request.user,
            )
            msg = 'Shift planifi\u00e9'

        return JsonResponse({
            'success': True, 'message': msg,
            'planning': {
                'id': shift.id,
                'point_vente_id': affectation.point_vente_id,
                'point_vente': point_vente.nom,
                'employe_id': affectation.employe_id,
                'employe': employe.nom_complet,
                'date': debut_dt.strftime('%Y-%m-%d'),
                'heure_debut': debut_dt.strftime('%H:%M'),
                'heure_fin': fin_dt.strftime('%H:%M'),
                'statut': shift.statut,
                'notes': shift.notes or '',
            }
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_planning_supprimer(request):
    try:
        data = json.loads(request.body)
        shift = get_object_or_404(ShiftEmploye, id=data['id'])
        shift.delete()
        return JsonResponse({'success': True, 'message': 'Planning supprim\u00e9'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_planning_creer_masse(request):
    try:
        data = json.loads(request.body)
        employe_id = data.get('employe_id')
        point_vente_id = data.get('point_vente_id')
        date_debut_d = datetime.strptime(data['date_debut'], '%Y-%m-%d').date()
        date_fin_d = datetime.strptime(data['date_fin'], '%Y-%m-%d').date()
        heure_debut_t = datetime.strptime(data['heure_debut'], '%H:%M').time()
        heure_fin_t = datetime.strptime(data['heure_fin'], '%H:%M').time()
        jours_semaine = data.get('jours_semaine', [1, 2, 3, 4, 5, 6, 7])
        statut = data.get('statut', 'PLANIFIE')
        notes = data.get('notes', '')

        employe = get_object_or_404(Employe, id=employe_id)
        point_vente = get_object_or_404(PointVente, id=point_vente_id)

        affectation, _ = AffectationPointVente.objects.get_or_create(
            employe=employe, point_vente=point_vente,
            defaults={'role': 'CAISSIER', 'actif': True, 'peut_vendre': True, 'peut_encaisser': True},
        )

        if date_debut_d > date_fin_d:
            return JsonResponse({'success': False, 'error': 'La date de d\u00e9but doit \u00eatre avant la date de fin'})

        jour_map = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 7: 6}
        jours_filtre = [jour_map.get(j, j) for j in jours_semaine]

        created = []
        conflits = []

        current = date_debut_d
        while current <= date_fin_d:
            jour_sem = current.weekday()
            if jour_sem in jours_filtre:
                debut_dt = timezone.make_aware(datetime.combine(current, heure_debut_t))
                fin_dt = timezone.make_aware(datetime.combine(current, heure_fin_t))
                if fin_dt <= debut_dt:
                    fin_dt += timedelta(days=1)

                conflits_jour = _conflits_planning(affectation, debut_dt, fin_dt)
                if conflits_jour:
                    conflit = conflits_jour[0]
                    conflits.append({
                        'date': current.strftime('%Y-%m-%d'),
                        'existant_id': conflit.id,
                        'existant_heure': f"{conflit.debut_prevu.strftime('%H:%M')}-{conflit.fin_prevue.strftime('%H:%M')}",
                        'point_vente': conflit.affectation.point_vente.nom if conflit.affectation and conflit.affectation.point_vente else '',
                        'employe': conflit.affectation.employe.nom_complet if conflit.affectation and conflit.affectation.employe else '',
                    })
                else:
                    shift = ShiftEmploye.objects.create(
                        affectation=affectation,
                        debut_prevu=debut_dt, fin_prevue=fin_dt,
                        statut=statut, notes=notes, cree_par=request.user,
                    )
                    created.append({
                        'id': shift.id, 'date': shift.debut_prevu.strftime('%Y-%m-%d'),
                        'heure_debut': shift.debut_prevu.strftime('%H:%M'),
                        'heure_fin': shift.fin_prevue.strftime('%H:%M'),
                        'statut': shift.statut,
                    })
            current += timedelta(days=1)

        return JsonResponse({
            'success': True,
            'message': f"{len(created)} planning(s) cr\u00e9\u00e9(s)",
            'created': created, 'conflits': conflits,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_planning_employes(request):
    point_id = request.GET.get('point_vente')
    if not point_id:
        return JsonResponse({'success': False, 'error': 'point_vente requis'})

    affectations = AffectationPointVente.objects.filter(
        point_vente_id=point_id, actif=True
    ).select_related('employe')
    employes = [a.employe for a in affectations if a.employe]

    from apps.rh.models import Pointage
    today = timezone.now().date()
    data = []
    for e in employes:
        pointage = Pointage.objects.filter(employe=e, date_pointage=today).first()
        data.append({
            'id': e.id, 'matricule': e.matricule,
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
    try:
        data = json.loads(request.body)
        employe_id = data.get('employe_id')
        heure_entree = data.get('heure_entree', '')
        heure_sortie = data.get('heure_sortie', '')

        employe = Employe.objects.get(id=employe_id, actif=True)
        from apps.rh.models import Pointage
        today = timezone.now().date()

        pointage, created = Pointage.objects.get_or_create(
            employe=employe, date_pointage=today,
            defaults={'id_pointage': f"PTG{today.strftime('%y%m%d')}{employe.matricule}"},
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
            'message': f'Horaire mis \u00e0 jour pour {employe.nom} {employe.prenom}'
        })

    except Employe.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Employ\u00e9 introuvable'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

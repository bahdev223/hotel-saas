from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.db.models import Max
from ..models import Poste, Employe
from ..permissions import user_can_gerer_rh


@login_required
def liste_postes(request):
    """Liste des postes"""
    if not user_can_gerer_rh(request.user):
        messages.error(request, "Accès réservé au personnel RH.")
        return redirect('dashboard:index')
    postes = Poste.objects.all()
    
    total_employes = Employe.objects.count()
    cadres = postes.filter(classification='Cadre').count()
    salaires = [p.salaire_base for p in postes if p.salaire_base]
    salaire_moyen = sum(salaires) / len(salaires) if salaires else 0
    
    context = {
        'postes': postes,
        'total_employes': total_employes,
        'cadres': cadres,
        'salaire_moyen': salaire_moyen,
    }
    return render(request, 'rh/postes/liste.html', context)


@csrf_exempt
@login_required
def api_prochain_code_poste(request):
    """Retourne le prochain code disponible"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    dernier = Poste.objects.aggregate(max_c=Max('code'))['max_c']
    if dernier and dernier.startswith('P-'):
        try:
            num = int(dernier.split('-')[1]) + 1
        except (ValueError, IndexError):
            num = Poste.objects.count() + 1
    else:
        num = Poste.objects.count() + 1
    return JsonResponse({'code': f'P-{num:03d}'})


@csrf_exempt
@login_required
def api_ajouter_poste(request):
    """API pour ajouter un poste"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            code = data.get('code')
            if not code:
                dernier = Poste.objects.aggregate(max_c=Max('code'))['max_c']
                if dernier and dernier.startswith('P-'):
                    try:
                        num = int(dernier.split('-')[1]) + 1
                    except (ValueError, IndexError):
                        num = Poste.objects.count() + 1
                else:
                    num = Poste.objects.count() + 1
                code = f'P-{num:03d}'
            poste = Poste.objects.create(
                code=code,
                intitule=data.get('intitule'),
                classification='Employe',
            )
            return JsonResponse({'success': True, 'poste_id': poste.id, 'code': code})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
def api_detail_poste(request, poste_id):
    """API pour récupérer un poste"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    try:
        poste = Poste.objects.get(id=poste_id)
        return JsonResponse({
            'success': True,
            'poste': {
                'id': poste.id,
                'code': poste.code,
                'intitule': poste.intitule,
                'classification': poste.classification,
                'coefficient': poste.coefficient,
                'niveau': poste.niveau,
                'salaire_base': float(poste.salaire_base) if poste.salaire_base else None
            }
        })
    except Poste.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Poste non trouvé'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def modifier_poste(request, poste_id):
    """Modifier un poste"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            poste = Poste.objects.get(id=poste_id)
            poste.code = data.get('code', poste.code)
            poste.intitule = data.get('intitule')
            poste.save()
            return JsonResponse({'success': True})
        except Poste.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Poste non trouvé'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@csrf_exempt
@login_required
def supprimer_poste(request, poste_id):
    """Supprimer un poste"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            poste = Poste.objects.get(id=poste_id)
            poste.delete()
            return JsonResponse({'success': True})
        except Poste.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Poste non trouvé'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


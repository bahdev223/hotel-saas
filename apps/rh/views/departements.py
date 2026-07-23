from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from ..models import Departement, Employe
from ..permissions import user_can_gerer_rh


@login_required
def liste_departements(request):
    """Liste des départements"""
    if not user_can_gerer_rh(request.user):
        messages.error(request, "Accès réservé au personnel RH.")
        return redirect('dashboard:index')
    departements = Departement.objects.filter(actif=True)
    employes = Employe.objects.filter(actif=True).order_by('nom', 'prenom')
    total_employes = Employe.objects.count()
    nb_depts = max(departements.count(), 1)
    context = {
        'departements': departements,
        'employes_list': employes,
        'total_employes': total_employes,
        'moy_employes': round(total_employes / nb_depts),
    }
    return render(request, 'rh/departements/liste.html', context)


@csrf_exempt
@login_required
def api_ajouter_departement(request):
    """API pour ajouter un département"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            dept = Departement.objects.create(
                code=data.get('code'),
                libelle=data.get('libelle'),
                responsable_id=data.get('responsable_id') or None,
                actif=True
            )
            return JsonResponse({'success': True, 'departement_id': dept.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
def api_detail_departement(request, dept_id):
    """API pour récupérer un département"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    try:
        dept = Departement.objects.get(id=dept_id)
        return JsonResponse({
            'success': True,
            'departement': {
                'id': dept.id,
                'code': dept.code,
                'libelle': dept.libelle,
                'responsable_id': dept.responsable_id
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
def supprimer_departement(request, dept_id):
    """Supprimer un département"""
    if not user_can_gerer_rh(request.user):
        return JsonResponse({'success': False, 'error': 'Accès non autorisé'}, status=403)
    if request.method == 'POST':
        try:
            dept = Departement.objects.get(id=dept_id)
            dept.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


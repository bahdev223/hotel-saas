from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from ..models import RubriquePaie


@login_required
def liste_rubriques(request):
    """Liste des rubriques"""
    rubriques = RubriquePaie.objects.all().order_by('ordre', 'code')
    return render(request, 'paie/rubriques/liste.html', {'rubriques': rubriques})


@csrf_exempt
def api_ajouter_rubrique(request):
    """API pour ajouter une rubrique"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            rubrique = RubriquePaie.objects.create(
                code=data.get('code'),
                libelle=data.get('libelle'),
                type_rubrique=data.get('type_rubrique'),
                sens=data.get('sens'),
                taux=data.get('taux') or None,
                montant_fixe=data.get('montant_fixe') or None,
                ordre=data.get('ordre', 0),
                actif=data.get('actif', True)
            )
            return JsonResponse({'success': True, 'rubrique_id': rubrique.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


def api_detail_rubrique(request, rubrique_id):
    """API pour récupérer une rubrique"""
    try:
        rubrique = RubriquePaie.objects.get(id=rubrique_id)
        return JsonResponse({
            'success': True,
            'rubrique': {
                'id': rubrique.id,
                'code': rubrique.code,
                'libelle': rubrique.libelle,
                'type_rubrique': rubrique.type_rubrique,
                'sens': rubrique.sens,
                'taux': float(rubrique.taux) if rubrique.taux else None,
                'montant_fixe': float(rubrique.montant_fixe) if rubrique.montant_fixe else None,
                'ordre': rubrique.ordre,
                'actif': rubrique.actif
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
def modifier_rubrique(request, rubrique_id):
    """Modifier une rubrique"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            rubrique = RubriquePaie.objects.get(id=rubrique_id)
            rubrique.code = data.get('code')
            rubrique.libelle = data.get('libelle')
            rubrique.type_rubrique = data.get('type_rubrique')
            rubrique.sens = data.get('sens')
            rubrique.taux = data.get('taux') or None
            rubrique.montant_fixe = data.get('montant_fixe') or None
            rubrique.ordre = data.get('ordre', 0)
            rubrique.actif = data.get('actif', True)
            rubrique.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@csrf_exempt
def supprimer_rubrique(request, rubrique_id):
    """Supprimer une rubrique"""
    if request.method == 'POST':
        try:
            rubrique = RubriquePaie.objects.get(id=rubrique_id)
            rubrique.delete()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@csrf_exempt
def toggle_rubrique(request, rubrique_id):
    """Activer/Désactiver une rubrique"""
    if request.method == 'POST':
        try:
            rubrique = RubriquePaie.objects.get(id=rubrique_id)
            rubrique.actif = not rubrique.actif
            rubrique.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})




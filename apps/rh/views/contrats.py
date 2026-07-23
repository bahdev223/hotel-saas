from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import uuid
from ..models import Contrat, Employe
from ..services.contrat_pdf import contrat_pdf_response


@login_required
def liste_contrats(request):
    """Liste des contrats"""
    contrats = Contrat.objects.filter(actif=True).select_related('employe')
    
    contrats_actifs = contrats.filter(actif=True).count()
    cdi_count = contrats.filter(type_contrat='CDI').count()
    salaires = [c.salaire_brut_mensuel for c in contrats if c.salaire_brut_mensuel]
    salaire_moyen = sum(salaires) / len(salaires) if salaires else 0
    
    context = {
        'contrats': contrats,
        'contrats_actifs': contrats_actifs,
        'cdi_count': cdi_count,
        'salaire_moyen': salaire_moyen,
        'employes': Employe.objects.filter(actif=True),
    }
    return render(request, 'rh/contrats/liste.html', context)


@csrf_exempt
def api_ajouter_contrat(request):
    """API pour ajouter un contrat"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            contrat = Contrat.objects.create(
                id_contrat=f"CT-{uuid.uuid4().hex[:8].upper()}",
                employe_id=data.get('employe_id'),
                type_contrat=data.get('type_contrat', 'CDI'),
                date_debut=data.get('date_debut'),
                date_fin=data.get('date_fin'),
                duree_heures_mois=data.get('duree_heures_mois', 151.67),
                salaire_brut_mensuel=data.get('salaire_brut_mensuel'),
                statut_cadre=data.get('statut_cadre', False),
                commentaire=data.get('commentaire', ''),
                actif=True
            )
            return JsonResponse({'success': True, 'contrat_id': contrat.id_contrat})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
def contrat_pdf(request, id_contrat):
    contrat = get_object_or_404(Contrat, id_contrat=id_contrat)
    return contrat_pdf_response(contrat)


@csrf_exempt
def api_detail_contrat(request, id_contrat):
    contrat = get_object_or_404(Contrat, id_contrat=id_contrat)
    return JsonResponse({
        'success': True,
        'contrat': {
            'id_contrat': contrat.id_contrat,
            'employe_id': contrat.employe_id,
            'type_contrat': contrat.type_contrat,
            'date_debut': contrat.date_debut.isoformat(),
            'date_fin': contrat.date_fin.isoformat() if contrat.date_fin else None,
            'duree_heures_mois': float(contrat.duree_heures_mois),
            'salaire_brut_mensuel': float(contrat.salaire_brut_mensuel) if contrat.salaire_brut_mensuel else None,
            'statut_cadre': contrat.statut_cadre,
            'commentaire': contrat.commentaire or '',
            'actif': contrat.actif,
        }
    })


@csrf_exempt
@require_POST
def api_modifier_contrat(request, id_contrat):
    try:
        contrat = get_object_or_404(Contrat, id_contrat=id_contrat)
        data = json.loads(request.body)
        contrat.type_contrat = data.get('type_contrat', contrat.type_contrat)
        contrat.date_debut = data.get('date_debut', contrat.date_debut)
        contrat.date_fin = data.get('date_fin', contrat.date_fin)
        contrat.duree_heures_mois = data.get('duree_heures_mois', contrat.duree_heures_mois)
        contrat.salaire_brut_mensuel = data.get('salaire_brut_mensuel', contrat.salaire_brut_mensuel)
        contrat.statut_cadre = data.get('statut_cadre', contrat.statut_cadre)
        contrat.commentaire = data.get('commentaire', contrat.commentaire)
        contrat.actif = data.get('actif', contrat.actif)
        contrat.save()
        return JsonResponse({'success': True, 'contrat_id': contrat.id_contrat})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@require_POST
def api_supprimer_contrat(request, id_contrat):
    try:
        contrat = get_object_or_404(Contrat, id_contrat=id_contrat)
        contrat.actif = False
        contrat.save()
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})



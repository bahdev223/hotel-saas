from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
import json
import uuid
from ..models import Conge, Employe


@login_required
def liste_conges(request):
    try:
        conges = Conge.objects.all().order_by('-date_demande')
        context = {
            'conges': conges,
            'total': conges.count(),
            'en_attente': conges.filter(statut='En attente').count(),
            'valides': conges.filter(statut='Validé').count(),
        }
        return render(request, 'rh/conges/liste.html', context)
    except Exception as e:
        messages.error(request, f'Erreur: {str(e)}')
        return redirect('rh:dashboard')


@login_required
def ajouter_conge(request):
    if request.method == 'POST':
        try:
            conge = Conge.objects.create(
                id_conge=f"CG-{uuid.uuid4().hex[:8].upper()}",
                employe_id=request.POST.get('employe_id'),
                date_debut=request.POST.get('date_debut'),
                date_fin=request.POST.get('date_fin'),
                nb_jours_ouvrables=int(request.POST.get('nb_jours_ouvrables')),
                commentaire=request.POST.get('commentaire', ''),
                statut='En attente'
            )
            messages.success(request, 'Demande de congé enregistrée')
            return redirect('rh:liste_conges')
        except Exception as e:
            messages.error(request, str(e))

    employes = Employe.objects.filter(actif=True)
    return render(request, 'rh/conges/ajouter.html', {'employes': employes})


@csrf_exempt
@require_POST
def api_valider_conge(request, id_conge):
    conge = get_object_or_404(Conge, id_conge=id_conge)
    conge.statut = 'Validé'
    conge.save()
    return JsonResponse({'success': True})


@csrf_exempt
@require_POST
def api_refuser_conge(request, id_conge):
    conge = get_object_or_404(Conge, id_conge=id_conge)
    conge.statut = 'Refusé'
    conge.save()
    return JsonResponse({'success': True})

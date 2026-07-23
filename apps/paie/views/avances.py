# apps/paie/views/avances.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.db.models import Sum
import json
import uuid
from datetime import date

from ..models import AvanceSalaire, LigneRemboursement
from apps.rh.models import Employe


@login_required
def liste_avances(request):
    """Liste des avances sur salaire"""
    avances = AvanceSalaire.objects.all()
    
    # Filtres
    statut = request.GET.get('statut')
    employe_id = request.GET.get('employe')
    
    if statut:
        avances = avances.filter(statut=statut)
    if employe_id:
        avances = avances.filter(employe_id=employe_id)
    
    context = {
        'avances': avances,
        'statuts': AvanceSalaire.STATUT_CHOICES,
        'employes': Employe.objects.filter(actif=True),
        'total_attente': avances.filter(statut='EN_ATTENTE').count(),
        'total_approuvees': avances.filter(statut='APPROUVEE').count(),
        'total_payees': avances.filter(statut='PAYEE').count(),
    }
    return render(request, 'paie/avances/liste.html', context)


@login_required
def ajouter_avance(request):
    """Ajouter une demande d'avance"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            avance = AvanceSalaire.objects.create(
                id=str(uuid.uuid4())[:8],
                employe_id=data.get('employe_id'),
                montant=data.get('montant'),
                motif=data.get('motif'),
                mois_remboursement=int(data.get('mois_remboursement')),
                annee_remboursement=int(data.get('annee_remboursement')),
                nombre_mois=int(data.get('nombre_mois', 1))
            )
            
            # Créer les lignes de remboursement
            mensualite = avance.mensualite
            for i in range(avance.nombre_mois):
                mois_remb = avance.mois_remboursement + i
                annee_remb = avance.annee_remboursement
                if mois_remb > 12:
                    mois_remb -= 12
                    annee_remb += 1
                
                LigneRemboursement.objects.create(
                    avance=avance,
                    mois=mois_remb,
                    annee=annee_remb,
                    montant=mensualite,
                    rembourse=False
                )
            
            return JsonResponse({'success': True, 'avance_id': avance.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    
    context = {
        'employes': Employe.objects.filter(actif=True),
    }
    return render(request, 'paie/avances/ajouter.html', context)


@login_required
def approuver_avance(request, avance_id):
    """Approuver une avance"""
    avance = get_object_or_404(AvanceSalaire, id=avance_id)
    
    if request.method == 'POST':
        avance.statut = 'APPROUVEE'
        avance.date_approbation = date.today()
        avance.approuve_par = request.user.username
        avance.save()
        messages.success(request, f'Avance approuvée pour {avance.employe.nom}')
    
    return redirect('paie:liste_avances')


@login_required
def payer_avance(request, avance_id):
    """Marquer l'avance comme payée"""
    avance = get_object_or_404(AvanceSalaire, id=avance_id)
    
    if request.method == 'POST':
        avance.statut = 'PAYEE'
        avance.date_paiement = date.today()
        avance.save()
        messages.success(request, f'Avance payée à {avance.employe.nom}')
    
    return redirect('paie:liste_avances')


@login_required
def rejeter_avance(request, avance_id):
    """Rejeter une avance"""
    avance = get_object_or_404(AvanceSalaire, id=avance_id)
    
    if request.method == 'POST':
        avance.statut = 'REJETEE'
        avance.save()
        messages.success(request, f'Avance rejetée pour {avance.employe.nom}')
    
    return redirect('paie:liste_avances')


@csrf_exempt
def api_detail_avance(request, avance_id):
    """API pour récupérer les détails d'une avance"""
    try:
        avance = AvanceSalaire.objects.get(id=avance_id)
        return JsonResponse({
            'success': True,
            'avance': {
                'id': avance.id,
                'employe_id': avance.employe_id,
                'employe_nom': avance.employe.nom,
                'employe_prenom': avance.employe.prenom,
                'montant': float(avance.montant),
                'motif': avance.motif,
                'mois_remboursement': avance.mois_remboursement,
                'annee_remboursement': avance.annee_remboursement,
                'nombre_mois': avance.nombre_mois,
                'mensualite': float(avance.mensualite),
                'statut': avance.statut,
                'date_demande': avance.date_demande.strftime('%d/%m/%Y')
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
    
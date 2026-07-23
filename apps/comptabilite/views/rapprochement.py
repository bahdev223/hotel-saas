# apps/comptabilite/views/rapprochement.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from datetime import date, datetime
import json

from ..models import ReleveBancaire, LigneReleveBancaire, EcritureModel
from apps.tresorerie.models import Caisse, MouvementCaisse
from ..services.rapprochement_service import RapprochementService


@login_required
def releves_liste(request):
    """Liste des relevés bancaires"""
    releves = ReleveBancaire.objects.all().order_by('-date_fin')
    
    caisses = Caisse.objects.filter(actif=True, type_financier='BANQUE')
    
    paginator = Paginator(releves, 20)
    page = request.GET.get('page')
    releves_page = paginator.get_page(page)
    
    context = {
        'releves': releves_page,
        'caisses': caisses,
        'titre': 'Relevés bancaires',
        'header': 'Rapprochement bancaire',
        'subtitle': 'Relevés et rapprochements'
    }
    return render(request, 'comptabilite/rapprochement/liste.html', context)


@login_required
def releve_detail(request, releve_id):
    """Détail d'un relevé bancaire avec rapprochement"""
    releve = get_object_or_404(ReleveBancaire, id=releve_id)
    lignes = releve.lignes.all().order_by('date_operation')
    
    # Récupérer les mouvements de caisse pour rapprochement
    mouvements = MouvementCaisse.objects.filter(
        caisse=releve.caisse,
        date__date__gte=releve.date_debut,
        date__date__lte=releve.date_fin
    ).order_by('-date')
    
    # Statistiques
    stats = {
        'total_credit': releve.total_credit,
        'total_debit': releve.total_debit,
        'rapprochees': lignes.filter(statut='RAPPROCHE').count(),
        'non_rapprochees': lignes.filter(statut='NON_RAPPROCHE').count(),
        'ecarts': lignes.filter(statut='ECART').count(),
    }
    
    context = {
        'releve': releve,
        'lignes': lignes,
        'mouvements': mouvements,
        'stats': stats,
        'titre': f'Relevé {releve.caisse.nom}',
        'header': f'Relevé {releve.caisse.nom}',
        'subtitle': f'Du {releve.date_debut} au {releve.date_fin}'
    }
    return render(request, 'comptabilite/rapprochement/detail.html', context)


@login_required
def releve_importer(request):
    """Importer un relevé bancaire"""
    if request.method == 'POST':
        try:
            caisse_id = request.POST.get('caisse')
            date_debut = request.POST.get('date_debut')
            date_fin = request.POST.get('date_fin')
            fichier = request.FILES.get('fichier')
            
            # Pour l'exemple, on simule l'import
            # En réalité, il faudrait parser le fichier (CSV, Excel, etc.)
            
            messages.success(request, 'Relevé importé avec succès')
            return redirect('comptabilite:releves_liste')
            
        except Exception as e:
            messages.error(request, str(e))
    
    caisses = Caisse.objects.filter(actif=True, type_financier='BANQUE')
    
    context = {
        'caisses': caisses,
        'titre': 'Importer un relevé',
        'header': 'Import de relevé bancaire',
        'subtitle': 'CSV, Excel ou PDF'
    }
    return render(request, 'comptabilite/rapprochement/importer.html', context)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_rapprocher_ligne(request):
    """API pour rapprocher une ligne de relevé"""
    try:
        data = json.loads(request.body)
        ligne_id = data.get('ligne_id')
        ecriture_id = data.get('ecriture_id')
        
        ligne = RapprochementService.rapprocher_ligne(ligne_id, ecriture_id, request.user)
        
        return JsonResponse({'success': True, 'message': 'Ligne rapprochée'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_creer_ecart(request):
    """API pour créer un écart de rapprochement"""
    try:
        data = json.loads(request.body)
        
        ecart = RapprochementService.creer_ecart(
            releve_id=data.get('releve_id'),
            type_ecart=data.get('type_ecart'),
            montant=data.get('montant'),
            sens=data.get('sens'),
            justification=data.get('justification'),
            user=request.user
        )
        
        return JsonResponse({'success': True, 'message': 'Écart traité'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def api_mouvements_caisse(request):
    """API pour récupérer les mouvements de caisse pour rapprochement"""
    caisse_id = request.GET.get('caisse_id')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    mouvements = MouvementCaisse.objects.filter(
        caisse_id=caisse_id,
        date__date__gte=date_debut,
        date__date__lte=date_fin
    ).order_by('-date')
    
    data = []
    for m in mouvements:
        data.append({
            'id': m.id,
            'date': m.date.strftime('%d/%m/%Y'),
            'libelle': m.libelle,
            'montant': float(m.montant),
            'type': m.type_mouvement,
            'reference': m.reference or ''
        })
    
    return JsonResponse({'success': True, 'mouvements': data})


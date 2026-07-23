# apps/comptabilite/views/amortissements.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
import json
import uuid

from ..models import Immobilisation, PlanAmortissement, CompteModel
from ..services.amortissement_service import AmortissementService


@login_required
def immobilisations_liste(request):
    """Liste des immobilisations"""
    immobilisations = Immobilisation.objects.all().order_by('-date_acquisition')
    
    # Filtres
    type_filter = request.GET.get('type')
    statut_filter = request.GET.get('statut')
    
    if type_filter:
        immobilisations = immobilisations.filter(type_immobilisation=type_filter)
    if statut_filter:
        immobilisations = immobilisations.filter(statut=statut_filter)
    
    # Statistiques
    stats = {
        'total': immobilisations.count(),
        'valeur_totale': sum(i.valeur_originale for i in immobilisations),
        'amortissement_annuel_total': sum(i.amortissement_annuel for i in immobilisations),
        'valeur_nette_totale': sum(i.valeur_nette_comptable() for i in immobilisations),
    }
    
    paginator = Paginator(immobilisations, 20)
    page = request.GET.get('page')
    immobilisations_page = paginator.get_page(page)
    
    context = {
        'immobilisations': immobilisations_page,
        'stats': stats,
        'types': Immobilisation.TYPE_CHOICES,
        'statuts': Immobilisation._meta.get_field('statut').choices,
        'type_filter': type_filter,
        'statut_filter': statut_filter,
        'titre': 'Immobilisations',
        'header': 'Gestion des immobilisations',
        'subtitle': 'Actifs fixes et amortissements'
    }
    return render(request, 'comptabilite/amortissements/liste.html', context)


@login_required
def immobilisation_ajouter(request):
    """Ajouter une immobilisation"""
    if request.method == 'POST':
        try:
            compte_immobilisation = CompteModel.objects.get(id=request.POST.get('compte_immobilisation'))
            compte_amortissement = CompteModel.objects.get(id=request.POST.get('compte_amortissement'))
            compte_charge = CompteModel.objects.get(id=request.POST.get('compte_charge'))
            
            immobilisation = Immobilisation.objects.create(
                code=request.POST.get('code'),
                libelle=request.POST.get('libelle'),
                type_immobilisation=request.POST.get('type_immobilisation'),
                date_acquisition=request.POST.get('date_acquisition'),
                valeur_originale=request.POST.get('valeur_originale'),
                valeur_residuelle=request.POST.get('valeur_residuelle', 0),
                duree_ans=int(request.POST.get('duree_ans')),
                compte_immobilisation=compte_immobilisation,
                compte_amortissement=compte_amortissement,
                compte_charge=compte_charge,
                notes=request.POST.get('notes', ''),
                statut='ACTIF'
            )
            
            # Générer le plan d'amortissement
            AmortissementService.generer_plan_amortissement(immobilisation.id)
            
            messages.success(request, f'Immobilisation {immobilisation.code} ajoutée')
            return redirect('comptabilite:immobilisations_liste')
            
        except Exception as e:
            messages.error(request, str(e))
    
    comptes_immobilisation = CompteModel.objects.filter(code__startswith='2', actif=True).order_by('code')
    comptes_amortissement = CompteModel.objects.filter(code__startswith='28', actif=True).order_by('code')
    comptes_charge = CompteModel.objects.filter(code__startswith='68', actif=True).order_by('code')
    
    context = {
        'types': Immobilisation.TYPE_CHOICES,
        'comptes_immobilisation': comptes_immobilisation,
        'comptes_amortissement': comptes_amortissement,
        'comptes_charge': comptes_charge,
        'titre': 'Nouvelle immobilisation',
        'header': 'Ajouter une immobilisation',
        'subtitle': 'Enregistrement d\'un nouvel actif fixe'
    }
    return render(request, 'comptabilite/amortissements/ajouter.html', context)


@login_required
def immobilisation_detail(request, immobilisation_id):
    """Détail d'une immobilisation"""
    immobilisation = get_object_or_404(Immobilisation, id=immobilisation_id)
    plan = immobilisation.plan_amortissement.all().order_by('periode')
    
    # Calcul des amortissements déjà générés
    amortissements_generes = plan.filter(ecriture_generee=True)
    
    context = {
        'immobilisation': immobilisation,
        'plan': plan,
        'amortissements_generes': amortissements_generes,
        'titre': f'Immobilisation {immobilisation.code}',
        'header': immobilisation.libelle,
        'subtitle': f'Aquisition le {immobilisation.date_acquisition}'
    }
    return render(request, 'comptabilite/amortissements/detail.html', context)


@login_required
def generer_ecriture_amortissement(request, plan_id):
    """Générer l'écriture d'amortissement pour une période"""
    if request.method == 'POST':
        try:
            ecriture = AmortissementService.generer_ecriture_amortissement(plan_id, request.user)
            messages.success(request, f'Écriture {ecriture.reference} générée')
        except Exception as e:
            messages.error(request, str(e))
    
    return redirect('comptabilite:immobilisation_detail', immobilisation_id=request.POST.get('immobilisation_id'))


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def api_amortissements_mois(request):
    """API pour les amortissements du mois (dashboard)"""
    from datetime import date
    mois = int(request.GET.get('mois', date.today().month))
    annee = int(request.GET.get('annee', date.today().year))
    
    data = AmortissementService.get_amortissements_mensuels(annee, mois)
    
    return JsonResponse({
        'success': True,
        'total': float(data['total']),
        'periode': data['periode'].strftime('%B %Y'),
        'details': [
            {
                'code': p.immobilisation.code,
                'libelle': p.immobilisation.libelle,
                'montant': float(p.montant)
            }
            for p in data['plans']
        ]
    })
    
    
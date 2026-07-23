# apps/comptabilite/views/api.py
import json
import uuid
from decimal import Decimal
from datetime import datetime
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import transaction
from ..models import CompteModel, EcritureModel, LigneEcritureModel, JournalModel, ExerciceModel


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_ajouter_compte(request):
    """API pour ajouter un compte"""
    try:
        data = json.loads(request.body)
        code = data.get('code')
        libelle = data.get('libelle')
        nature = data.get('nature', 'ACTIF')
        sens = data.get('sens', 'DEBIT')
        categorie = data.get('categorie', 'bilan')
        
        if not code or not libelle:
            return JsonResponse({'success': False, 'error': 'Code et libellé requis'})
        
        if CompteModel.objects.filter(code=code).exists():
            return JsonResponse({'success': False, 'error': f'Le code {code} existe déjà'})
        
        compte = CompteModel.objects.create(
            code=code,
            libelle=libelle,
            nature=nature,
            sens=sens,
            type_compte='compte',
            categorie=categorie,
            est_mouvement=True,
            actif=True
        )
        
        return JsonResponse({'success': True, 'compte_id': compte.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_ajouter_sous_compte(request):
    """API pour ajouter un sous-compte"""
    try:
        data = json.loads(request.body)
        parent_id = data.get('parent_id')
        code = data.get('code')
        libelle = data.get('libelle')
        
        if not code or not libelle or not parent_id:
            return JsonResponse({'success': False, 'error': 'Tous les champs sont requis'})
        
        if CompteModel.objects.filter(code=code).exists():
            return JsonResponse({'success': False, 'error': f'Le code {code} existe déjà'})
        
        parent = CompteModel.objects.get(id=parent_id)
        
        compte = CompteModel.objects.create(
            code=code,
            libelle=libelle,
            nature=parent.nature,
            sens=parent.sens,
            parent=parent,
            niveau=parent.niveau + 1,
            type_compte='sous_compte',
            categorie=parent.categorie,
            est_mouvement=True,
            actif=True
        )
        
        return JsonResponse({'success': True, 'compte_id': compte.id})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# ========== NOUVEAU : API POUR ÉCRITURE MANUELLE ==========

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_creer_ecriture_manuelle(request):
    """API pour créer une écriture comptable manuelle"""
    try:
        data = json.loads(request.body)
        
        # Validation des champs obligatoires
        date_ecriture = data.get('date_ecriture')
        journal_id = data.get('journal_id')
        libelle = data.get('libelle')
        lignes = data.get('lignes', [])
        
        if not date_ecriture:
            return JsonResponse({'success': False, 'error': 'La date est requise'}, status=400)
        
        if not journal_id:
            return JsonResponse({'success': False, 'error': 'Le journal est requis'}, status=400)
        
        if not libelle:
            return JsonResponse({'success': False, 'error': 'Le libellé est requis'}, status=400)
        
        if not lignes:
            return JsonResponse({'success': False, 'error': 'Ajoutez au moins une ligne'}, status=400)
        
        total_debit = Decimal('0')
        total_credit = Decimal('0')
        
        # Calculer les totaux et valider les lignes
        for ligne in lignes:
            debit = Decimal(str(ligne.get('debit', 0)))
            credit = Decimal(str(ligne.get('credit', 0)))
            
            if debit and credit:
                return JsonResponse({'success': False, 'error': 'Une ligne ne peut avoir débit ET crédit'}, status=400)
            
            if debit == 0 and credit == 0:
                return JsonResponse({'success': False, 'error': 'Le montant de la ligne est requis'}, status=400)
            
            total_debit += debit
            total_credit += credit
        
        # Vérifier l'équilibre
        if total_debit != total_credit:
            return JsonResponse({
                'success': False, 
                'error': f'Écriture déséquilibrée: Débit={total_debit:,.0f} F, Crédit={total_credit:,.0f} F'
            }, status=400)
        
        with transaction.atomic():
            # Récupérer l'exercice courant
            exercice = ExerciceModel.objects.filter(
                date_debut__lte=date_ecriture,
                date_fin__gte=date_ecriture,
                cloture=False
            ).first()
            
            if not exercice:
                return JsonResponse({'success': False, 'error': 'Aucun exercice ouvert pour cette période'}, status=400)
            
            # Récupérer le journal
            try:
                journal = JournalModel.objects.get(id=journal_id, actif=True)
            except JournalModel.DoesNotExist:
                return JsonResponse({'success': False, 'error': 'Journal non trouvé'}, status=400)
            
            # Générer une référence unique
            reference = f"MAN-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"
            
            # Créer l'écriture
            ecriture = EcritureModel.objects.create(
                reference=reference,
                date_ecriture=date_ecriture,
                libelle=libelle,
                journal=journal,
                piece=data.get('piece', ''),
                exercice=exercice,
                validee=True,
                date_validation=datetime.now(),
                created_by=request.user.username
            )
            
            # Créer les lignes
            for ligne in lignes:
                compte_id = ligne.get('compte_id')
                debit = Decimal(str(ligne.get('debit', 0)))
                credit = Decimal(str(ligne.get('credit', 0)))
                ligne_libelle = ligne.get('libelle', '')
                
                if not compte_id:
                    continue
                
                LigneEcritureModel.objects.create(
                    ecriture=ecriture,
                    compte_id=compte_id,
                    debit=debit,
                    credit=credit,
                    libelle=ligne_libelle
                )
            
            return JsonResponse({
                'success': True, 
                'message': f'Écriture {reference} créée avec succès',
                'ecriture_id': ecriture.id,
                'reference': reference
            })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def api_liste_comptes(request):
    """API pour récupérer la liste des comptes (pour le select)"""
    try:
        comptes = CompteModel.objects.filter(actif=True, est_mouvement=True).order_by('code')
        data = [
            {'id': c.id, 'code': c.code, 'libelle': c.libelle}
            for c in comptes
        ]
        return JsonResponse({'success': True, 'comptes': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@csrf_exempt
@require_http_methods(["GET"])
def api_liste_journaux(request):
    """API pour récupérer la liste des journaux (pour le select)"""
    try:
        journaux = JournalModel.objects.filter(actif=True).order_by('code')
        data = [
            {'id': j.id, 'code': j.code, 'libelle': j.libelle, 'type': j.type_journal}
            for j in journaux
        ]
        return JsonResponse({'success': True, 'journaux': data})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
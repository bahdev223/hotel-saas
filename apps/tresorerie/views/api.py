# apps/tresorerie/views/api.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from ..models import Caisse, MouvementCaisse
from ..services import MouvementService
from ..services.compte_financier_service import CompteFinancierService
import json


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_ajouter_caisse(request):
    """API pour ajouter une caisse"""
    try:
        data = json.loads(request.body)
        nom = data.get('nom')
        type_financier = data.get('type_financier', 'ESPECES')
        role = data.get('role') or None
        actif = data.get('actif', True)
        
        if not nom:
            return JsonResponse({'success': False, 'error': 'Nom obligatoire'})
        
        prefixe = 'CMPT'
        dernier = Caisse.objects.filter(code__startswith=prefixe).order_by('code').last()
        if dernier:
            try:
                num = int(dernier.code.replace(prefixe + '-', '')) + 1
            except ValueError:
                num = Caisse.objects.count() + 1
        else:
            num = 1
        code = f"{prefixe}-{num:03d}"
        
        caisse = Caisse.objects.create(
            code=code, nom=nom,
            type_financier=type_financier, role=role,
            actif=actif
        )
        caisse.compte_comptable = CompteFinancierService.generer_compte_comptable(caisse)
        caisse.full_clean()
        caisse.save(update_fields=['compte_comptable'])
        
        return JsonResponse({'success': True, 'caisse_id': caisse.id, 'message': f'{caisse.nom} créé'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_liste_caisses(request):
    """API pour récupérer la liste des caisses"""
    caisses = Caisse.objects.filter(actif=True).order_by('code')
    data = []
    for caisse in caisses:
        data.append({
            'id': caisse.id,
            'code': caisse.code,
            'nom': caisse.nom,
            'type': caisse.type_financier,
            'solde': float(caisse.solde),
            'est_caisse': caisse.est_caisse,
            'est_banque': caisse.est_banque,
            'est_mobile_money': caisse.est_mobile_money,
        })
    return JsonResponse({'success': True, 'caisses': data})


@login_required
def api_detail_caisse(request, caisse_id):
    """API pour récupérer les détails d'une caisse"""
    try:
        caisse = Caisse.objects.get(id=caisse_id, actif=True)
        return JsonResponse({
            'success': True,
            'caisse': {
                'id': caisse.id,
                'code': caisse.code,
                'nom': caisse.nom,
                'type': caisse.type_financier,
                'solde': float(caisse.solde),
                'est_caisse': caisse.est_caisse,
                'est_banque': caisse.est_banque,
                'est_mobile_money': caisse.est_mobile_money,
                'type_financier': caisse.type_financier,
                'role': caisse.role,
                'est_caisse': caisse.est_caisse,
                'est_banque': caisse.est_banque,
                'compte_comptable': {
                    'id': caisse.compte_comptable.id if caisse.compte_comptable else None,
                    'code': caisse.compte_comptable.code if caisse.compte_comptable else None,
                    'libelle': caisse.compte_comptable.libelle if caisse.compte_comptable else None,
                } if caisse.compte_comptable else None
            }
        })
    except Caisse.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Caisse non trouvée'}, status=404)


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_mouvement_caisse(request):
    """API pour enregistrer un mouvement de caisse (entrée/sortie)"""
    try:
        data = json.loads(request.body)
        caisse_id = data.get('caisse_id')
        type_mouvement = data.get('type_mouvement', 'ENTREE')
        montant = Decimal(str(data.get('montant', 0)))
        libelle = data.get('libelle', '')
        reference = data.get('reference', '')
        
        if not caisse_id or montant <= 0:
            return JsonResponse({'success': False, 'error': 'Paramètres invalides'})
        
        caisse = Caisse.objects.get(id=caisse_id, actif=True)
        
        if type_mouvement == 'ENTREE':
            mouvement = MouvementService.encaisser(
                caisse=caisse,
                montant=montant,
                libelle=libelle,
                user=request.user,
                reference=reference
            )
        else:
            mouvement = MouvementService.decaisser(
                caisse=caisse,
                montant=montant,
                libelle=libelle,
                user=request.user,
                reference=reference
            )
        
        return JsonResponse({
            'success': True,
            'mouvement_id': mouvement.id,
            'nouveau_solde': float(caisse.solde),
            'message': f'{type_mouvement} de {montant:,.0f} F enregistrée'
        })
        
    except Caisse.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Caisse non trouvée'}, status=404)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def api_historique_caisse(request, caisse_id):
    """API pour récupérer l'historique des mouvements d'une caisse"""
    try:
        caisse = Caisse.objects.get(id=caisse_id)
        mouvements = MouvementCaisse.objects.filter(caisse=caisse).order_by('-date')[:50]
        
        data = []
        for mvt in mouvements:
            data.append({
                'id': mvt.id,
                'date': mvt.date.strftime('%d/%m/%Y %H:%M'),
                'type': mvt.type_mouvement,
                'montant': float(mvt.montant),
                'libelle': mvt.libelle,
                'reference': mvt.reference,
                'created_by': mvt.created_by.username if mvt.created_by else None
            })
        
        return JsonResponse({
            'success': True,
            'caisse': {
                'id': caisse.id,
                'code': caisse.code,
                'nom': caisse.nom,
                'solde': float(caisse.solde)
            },
            'mouvements': data
        })
    except Caisse.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Caisse non trouvée'}, status=404)


@login_required
def api_synthese_caisses(request):
    """API pour la synthèse globale des caisses"""
    caisses_physiques = Caisse.objects.filter(type_financier='ESPECES', actif=True)
    banques = Caisse.objects.filter(type_financier='BANQUE', actif=True)
    
    total_especes = sum(c.solde for c in caisses_physiques)
    total_banque = sum(c.solde for c in banques)
    
    # Mouvements du jour (hors banques)
    today = timezone.now().date()
    mouvements_jour = MouvementCaisse.objects.filter(date__date=today).exclude(caisse__type_financier='BANQUE')

    entree_jour = mouvements_jour.filter(type_mouvement='ENTREE').aggregate(total=models.Sum('montant'))['total'] or 0
    sortie_jour = mouvements_jour.filter(type_mouvement='SORTIE').aggregate(total=models.Sum('montant'))['total'] or 0
    
    return JsonResponse({
        'success': True,
        'synthese': {
            'total_especes': float(total_especes),
            'total_banque': float(total_banque),
            'total_general': float(total_especes + total_banque),
            'entree_jour': float(entree_jour),
            'sortie_jour': float(sortie_jour),
            'flux_net_jour': float(entree_jour - sortie_jour)
        },
        'caisses': [{'id': c.id, 'code': c.code, 'nom': c.nom, 'solde': float(c.solde)} for c in caisses_physiques],
        'banques': [{'id': b.id, 'code': b.code, 'nom': b.nom, 'solde': float(b.solde)} for b in banques]
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_transfert_caisse(request):
    """API pour transférer de l'argent entre caisses"""
    try:
        data = json.loads(request.body)
        source_id = data.get('source_id')
        destination_id = data.get('destination_id')
        montant = Decimal(str(data.get('montant', 0)))
        libelle = data.get('libelle', '')
        
        if not source_id or not destination_id or montant <= 0:
            return JsonResponse({'success': False, 'error': 'Paramètres invalides'})
        
        if source_id == destination_id:
            return JsonResponse({'success': False, 'error': 'Impossible de transférer vers la même caisse'})
        
        source = Caisse.objects.get(id=source_id, actif=True)
        destination = Caisse.objects.get(id=destination_id, actif=True)
        
        # Décaisser de la source
        MouvementService.decaisser(
            caisse=source,
            montant=montant,
            libelle=f'Transfert vers {destination.nom} - {libelle}',
            user=request.user,
            reference=f'TRF-{source.code}-{destination.code}'
        )
        
        # Encaisser dans la destination
        MouvementService.encaisser(
            caisse=destination,
            montant=montant,
            libelle=f'Transfert de {source.nom} - {libelle}',
            user=request.user,
            reference=f'TRF-{source.code}-{destination.code}'
        )
        
        return JsonResponse({
            'success': True,
            'message': f'Transfert de {montant:,.0f} F de {source.nom} vers {destination.nom} effectué',
            'source_solde': float(source.solde),
            'destination_solde': float(destination.solde)
        })
        
    except Caisse.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Caisse non trouvée'}, status=404)
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    
    
    
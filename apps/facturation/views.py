# apps/facturation/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse, HttpResponse
from django.db.models import Sum
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
import json
from decimal import Decimal

from .models import FactureModel, LigneFactureModel
from .services import FactureActions, BaseFactureService
from apps.tresorerie.models import Caisse
from apps.paiements.models import Paiement


@login_required
def dashboard(request):
    """Dashboard facturation"""
    caisses = Caisse.objects.filter(actif=True)
    context = {'caisses': caisses}
    return render(request, 'facturation/dashboard.html', context)


@login_required
def liste_factures(request):
    """Liste des factures"""
    factures = FactureModel.objects.all().order_by('-date_emission')
    context = {'factures': factures}
    return render(request, 'facturation/liste.html', context)


@login_required
def detail_facture(request, facture_id):
    """Détail d'une facture"""
    facture = get_object_or_404(FactureModel, id=facture_id)
    
    content_type = ContentType.objects.get_for_model(FactureModel)
    paiements = Paiement.objects.filter(
        content_type=content_type,
        object_id=str(facture.id),
        statut='VALIDE',
        sens='ENTREE'
    ).order_by('-date')
    
    total_paye = facture.total_paye
    reste_a_payer = facture.reste_a_payer
    
    context = {
        'facture': facture,
        'paiements': paiements,
        'total_paye': total_paye,
        'reste_a_payer': reste_a_payer,
        'caisses': Caisse.objects.filter(actif=True),
    }
    return render(request, 'facturation/detail.html', context)


@login_required
def creer_facture(request):
    """Créer une facture manuelle avec lignes"""
    if request.method == 'POST':
        try:
            client_nom = request.POST.get('client_nom')
            if not client_nom:
                messages.error(request, 'Le nom du client est obligatoire')
                return redirect('facturation:creer')
            
            facture = BaseFactureService.creer_facture(
                client_nom=client_nom,
                notes=request.POST.get('notes', '')
            )
            contact = request.POST.get('client_contact', '')
            if contact:
                facture.client_contact = contact
                facture.save(update_fields=['client_contact'])
            
            lignes_json = request.POST.get('lignes_json', '[]')
            if lignes_json:
                lignes = json.loads(lignes_json)
                for ligne in lignes:
                    description = ligne.get('description', '').strip()
                    if description:
                        BaseFactureService.ajouter_ligne(
                            facture=facture,
                            description=description,
                            quantite=Decimal(str(ligne.get('quantite', 1))),
                            prix_unitaire=Decimal(str(ligne.get('prix_unitaire', 0))),
                            tva=Decimal(str(ligne.get('tva', 18)))
                        )
            
            messages.success(request, f'Facture {facture.numero} créée')
            return redirect('facturation:detail', facture_id=facture.id)
            
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    
    return render(request, 'facturation/creer.html')


@login_required
def modifier_facture(request, facture_id):
    """Modifier une facture"""
    facture = get_object_or_404(FactureModel, id=facture_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'sauvegarder':
            facture.client_nom = request.POST.get('client_nom', facture.client_nom)
            facture.client_contact = request.POST.get('client_contact', '')
            facture.notes = request.POST.get('notes', '')
            facture.save()
            
            lignes_json = request.POST.get('lignes_json', '[]')
            if lignes_json:
                lignes = json.loads(lignes_json)
                # Supprimer les anciennes lignes
                facture.lignes.all().delete()
                for ligne in lignes:
                    description = ligne.get('description', '').strip()
                    if description:
                        BaseFactureService.ajouter_ligne(
                            facture=facture,
                            description=description,
                            quantite=Decimal(str(ligne.get('quantite', 1))),
                            prix_unitaire=Decimal(str(ligne.get('prix_unitaire', 0))),
                            tva=Decimal(str(ligne.get('tva', 18)))
                        )
            messages.success(request, 'Facture modifiée')
            return redirect('facturation:detail', facture_id=facture.id)
            
        elif action == 'emettre':
            facture.emettre()
            messages.success(request, 'Facture émise')
            return redirect('facturation:detail', facture_id=facture.id)
    
    context = {'facture': facture}
    return render(request, 'facturation/modifier.html', context)


@login_required
def annuler_facture(request, facture_id):
    """Annuler une facture"""
    facture = get_object_or_404(FactureModel, id=facture_id)
    
    if request.method == 'POST':
        facture.annuler()
        messages.success(request, 'Facture annulée')
        return redirect('facturation:detail', facture_id=facture.id)
    
    context = {'facture': facture}
    return render(request, 'facturation/annuler.html', context)


@login_required
def export_pdf(request, facture_id):
    """Exporter une facture en PDF"""
    facture = get_object_or_404(FactureModel, id=facture_id)
    return HttpResponse(f"PDF de la facture {facture.numero} à générer", content_type='text/plain')


@login_required
def ajouter_paiement(request, facture_id):
    """Ajouter un paiement (redirection vers détail)"""
    return redirect('facturation:detail', facture_id=facture_id)


@login_required
def statistiques(request):
    """Statistiques facturation"""
    return render(request, 'facturation/statistiques.html')


# ========== API ==========

@login_required
def api_factures(request):
    """API liste des factures avec filtres"""
    factures = FactureModel.objects.all().order_by('-date_emission')
    
    categorie = request.GET.get('categorie')
    if categorie in ('CLIENT', 'FOURNISSEUR'):
        factures = factures.filter(type=categorie)
    
    type_fact = request.GET.get('type')
    if type_fact == 'COMMANDE':
        factures = factures.filter(commande__isnull=False)
    elif type_fact == 'LOCATION':
        factures = factures.filter(location__isnull=False)
    elif type_fact == 'MANUELLE':
        factures = factures.filter(commande__isnull=True, location__isnull=True)
    
    statut = request.GET.get('statut')
    if statut:
        factures = factures.filter(statut=statut)
    
    data = []
    for f in factures:
        data.append({
            'id': f.id,
            'numero': f.numero,
            'client_nom': f.client_nom,
            'date_emission': f.date_emission.isoformat(),
            'montant_total': float(f.montant_total),
            'total_paye': float(f.total_paye),
            'reste_a_payer': float(f.reste_a_payer),
            'statut': f.statut,
            'type': f.type_facture,
            'categorie': f.type,
        })
    return JsonResponse({'success': True, 'factures': data})


@login_required
def api_stats(request):
    """API statistiques"""
    from datetime import date
    
    factures = FactureModel.objects.all()
    mois_courant = date.today().month
    annee_courante = date.today().year
    
    ca_mois = 0
    for f in factures.filter(statut='PAYEE', date_emission__year=annee_courante, date_emission__month=mois_courant):
        ca_mois += float(f.montant_total)
    
    stats = {
        'total_factures': factures.count(),
        'en_cours': factures.filter(statut='EMISE').count(),
        'payees': factures.filter(statut='PAYEE').count(),
        'ca_mois': ca_mois
    }
    return JsonResponse({'success': True, 'stats': stats})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_paiement(request, facture_id):
    """API enregistrer un paiement"""
    try:
        data = json.loads(request.body)
        facture = get_object_or_404(FactureModel, id=facture_id)
        
        montant = Decimal(str(data.get('montant', 0)))
        mode = data.get('mode', 'ESPECES')
        caisse_id = data.get('caisse_id')
        notes = data.get('notes', '')
        
        if montant <= 0:
            return JsonResponse({'success': False, 'error': 'Montant invalide'})
        
        if montant > facture.reste_a_payer:
            return JsonResponse({
                'success': False,
                'error': f'Montant trop élevé. Reste à payer: {facture.reste_a_payer:,.0f} F'
            })
        
        caisse = None
        if caisse_id:
            caisse = get_object_or_404(Caisse, id=caisse_id)
        
        content_type = ContentType.objects.get_for_model(facture)
        
        paiement = Paiement.objects.create(
            reference=f"PAY-{facture.numero}-{timezone.now().strftime('%H%M%S')}",
            type_paiement='VENTE',
            montant=montant,
            sens='ENTREE',
            mode=mode,
            caisse=caisse,
            content_type=content_type,
            object_id=str(facture.id),
            created_by=request.user,
            notes=notes,
            statut='BROUILLON'
        )
        
        paiement.valider(request.user)
        FactureActions.verifier_et_mettre_a_jour_statut(facture)
        
        return JsonResponse({
            'success': True,
            'message': f'Paiement de {montant:,.0f} F enregistré',
            'reste_a_payer': float(facture.reste_a_payer),
            'est_payee': facture.est_payee
        })
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


# ========== API LIGNES ==========

@login_required
def api_lignes(request, facture_id):
    """API liste des lignes d'une facture"""
    facture = get_object_or_404(FactureModel, id=facture_id)
    lignes = []
    for l in facture.lignes.all():
        lignes.append({
            'id': l.id,
            'description': l.description,
            'quantite': float(l.quantite),
            'prix_unitaire': float(l.prix_unitaire),
            'tva': float(l.tva),
            'total_ttc': float(l.total_ttc),
        })
    return JsonResponse({'success': True, 'lignes': lignes})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_ajouter_ligne(request, facture_id):
    """API ajouter une ligne à une facture"""
    try:
        data = json.loads(request.body)
        facture = get_object_or_404(FactureModel, id=facture_id)
        
        ligne = BaseFactureService.ajouter_ligne(
            facture=facture,
            description=data.get('description', ''),
            quantite=Decimal(str(data.get('quantite', 1))),
            prix_unitaire=Decimal(str(data.get('prix_unitaire', 0))),
            tva=Decimal(str(data.get('tva', 18)))
        )
        
        return JsonResponse({
            'success': True,
            'ligne': {
                'id': ligne.id,
                'description': ligne.description,
                'quantite': float(ligne.quantite),
                'prix_unitaire': float(ligne.prix_unitaire),
                'tva': float(ligne.tva),
                'total_ttc': float(ligne.total_ttc),
            },
            'montant_total': float(facture.montant_total),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_supprimer_ligne(request, ligne_id):
    """API supprimer une ligne de facture"""
    try:
        ligne = get_object_or_404(LigneFactureModel, id=ligne_id)
        facture = ligne.facture
        ligne.delete()
        return JsonResponse({
            'success': True,
            'montant_total': float(facture.montant_total),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_detail_ligne(request, ligne_id):
    """API détail d'une ligne"""
    ligne = get_object_or_404(LigneFactureModel, id=ligne_id)
    return JsonResponse({
        'success': True,
        'ligne': {
            'id': ligne.id,
            'description': ligne.description,
            'quantite': float(ligne.quantite),
            'prix_unitaire': float(ligne.prix_unitaire),
            'tva': float(ligne.tva),
            'total_ttc': float(ligne.total_ttc),
        }
    })


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_modifier_ligne(request, ligne_id):
    """API modifier une ligne de facture"""
    try:
        data = json.loads(request.body)
        ligne = get_object_or_404(LigneFactureModel, id=ligne_id)
        ligne.description = data.get('description', ligne.description)
        ligne.quantite = Decimal(str(data.get('quantite', ligne.quantite)))
        ligne.prix_unitaire = Decimal(str(data.get('prix_unitaire', ligne.prix_unitaire)))
        ligne.tva = Decimal(str(data.get('tva', ligne.tva)))
        ligne.save()
        
        return JsonResponse({
            'success': True,
            'ligne': {
                'id': ligne.id,
                'description': ligne.description,
                'quantite': float(ligne.quantite),
                'prix_unitaire': float(ligne.prix_unitaire),
                'tva': float(ligne.tva),
                'total_ttc': float(ligne.total_ttc),
            },
            'montant_total': float(ligne.facture.montant_total),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

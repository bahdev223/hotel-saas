# apps/paiements/views.py
from datetime import date
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.db.models import Sum
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from .models import Paiement
from .services.paiement_engine import PaiementEngine, SessionRequiseError


@login_required
def liste_paiements(request):
    """Liste des paiements"""
    paiements = Paiement.objects.all().order_by('-date')

    paginator = Paginator(paiements, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)

    # Statistiques
    today = date.today()
    stats = {
        'total_aujourdhui': Paiement.objects.filter(date__date=today).aggregate(Sum('montant'))['montant__sum'] or 0,
        'total_mois': Paiement.objects.filter(date__month=today.month).aggregate(Sum('montant'))['montant__sum'] or 0,
        'total_annee': Paiement.objects.filter(date__year=today.year).aggregate(Sum('montant'))['montant__sum'] or 0,
    }

    context = {
        'paiements': page_obj,
        'stats': stats,
    }
    return render(request, 'paiements/liste.html', context)


@login_required
def detail_paiement(request, paiement_id):
    """Détail d'un paiement"""
    paiement = get_object_or_404(Paiement, id=paiement_id)
    return render(request, 'paiements/detail.html', {'paiement': paiement})


@login_required
def annuler_paiement(request, paiement_id):
    """Annuler un paiement"""
    paiement = get_object_or_404(Paiement, id=paiement_id)

    if request.method == 'POST':
        raison = request.POST.get('raison', '')
        paiement.annuler(request.user, raison)
        messages.success(request, f'Paiement {paiement.reference} annulé')
        return redirect('paiements:liste_paiements')

    return render(request, 'paiements/annuler.html', {'paiement': paiement})


@login_required
def api_stats_paiements(request):
    """API pour les statistiques de paiements"""
    today = date.today()

    stats = {
        'ca_jour': float(Paiement.objects.filter(date__date=today).aggregate(Sum('montant'))['montant__sum'] or 0),
        'ca_mois': float(Paiement.objects.filter(date__month=today.month).aggregate(Sum('montant'))['montant__sum'] or 0),
        'ca_annee': float(Paiement.objects.filter(date__year=today.year).aggregate(Sum('montant'))['montant__sum'] or 0),
        'total_paiements': Paiement.objects.count(),
    }

    return JsonResponse(stats)


# ========== PAYMENT ENGINE API ==========

@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_process_paiement(request):
    """API pour traiter un paiement via le moteur centralisé."""
    try:
        data = json.loads(request.body)
        try:
            paiement = PaiementEngine.encaisser(data, request.user)
        except SessionRequiseError as e:
            return JsonResponse({'success': False, 'error_code': 'SESSION_REQUISE', 'error': str(e)}, status=403)

        # Récupérer les infos facture/commande pour le reçu 80mm
        recu_data = {
            'id': paiement.id,
            'reference': paiement.reference,
            'montant': float(paiement.montant),
            'mode': paiement.mode,
            'mode_label': paiement.get_mode_display(),
            'date': paiement.date.isoformat(),
            'caisse': paiement.caisse.nom if paiement.caisse else '',
            'operateur': request.user.get_full_name() or request.user.username,
            'servi_par': request.user.get_full_name() or request.user.username,
            'point_vente': '',
        }

        # Résoudre les lignes de la source
        lignes = []
        source_numero = ''
        client_nom = ''
        if paiement.objet:
            obj = paiement.objet
            from apps.facturation.models import FactureModel
            if isinstance(obj, FactureModel):
                source_numero = obj.numero
                client_nom = obj.client_nom
                recu_data['point_vente'] = getattr(obj, 'point_vente_nom', '')
                for ligne in obj.lignes.all():
                    lignes.append({
                        'description': ligne.description,
                        'quantite': float(ligne.quantite),
                        'prix_unitaire': float(ligne.prix_unitaire),
                        'total_ttc': float(ligne.total_ttc),
                    })
            else:
                from apps.pos.models import Commande
                if isinstance(obj, Commande):
                    source_numero = obj.numero
                    client_nom = obj.client_nom or 'Anonyme'
                    recu_data['point_vente'] = obj.point_vente.nom if obj.point_vente else ''
                    recu_data['servi_par'] = obj.created_by.nom_complet if obj.created_by else recu_data['servi_par']
                    for ligne in obj.lignes.all():
                        lignes.append({
                            'description': ligne.article_nom,
                            'quantite': float(ligne.quantite),
                            'prix_unitaire': float(ligne.prix_unitaire),
                            'total_ttc': float(ligne.total_ligne),
                        })
                else:
                    client_nom = getattr(obj, 'nom', '')

        recu_data['source_numero'] = source_numero
        recu_data['client_nom'] = client_nom
        recu_data['lignes'] = lignes

        return JsonResponse({
            'success': True,
            'paiement': recu_data,
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def api_factures_impayees(request):
    """API liste des factures impayées pour le dialog paiement."""
    filtres = {}
    if request.GET.get('search'):
        filtres['search'] = request.GET['search']
    if request.GET.get('client_id'):
        filtres['client_id'] = request.GET['client_id']
    return JsonResponse({'success': True, 'factures': PaiementEngine.get_factures_impayees(filtres)})


@login_required
def api_commandes_impayees(request):
    """API liste des commandes impayées pour le dialog paiement."""
    filtres = {}
    if request.GET.get('search'):
        filtres['search'] = request.GET['search']
    if request.GET.get('point_vente_id'):
        filtres['point_vente_id'] = request.GET['point_vente_id']
    return JsonResponse({'success': True, 'commandes': PaiementEngine.get_commandes_impayees(filtres)})


@login_required
def api_solde_client(request, client_id):
    """API solde d'un client."""
    try:
        solde = PaiementEngine.get_solde_client(client_id)
        return JsonResponse({'success': True, 'solde': solde})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def api_dettes_client(request, client_id):
    """API dettes CREDIT d'un client."""
    from django.contrib.contenttypes.models import ContentType
    from apps.pos.models import Commande
    from apps.clients.models import Client

    try:
        client = Client.objects.get(id=client_id)
        ct_commande = ContentType.objects.get_for_model(Commande)

        paiements = Paiement.objects.filter(
            client=client, mode='CREDIT', statut='VALIDE'
        ).order_by('-date')

        dettes = []
        for p in paiements:
            commande = p.objet if isinstance(p.objet, Commande) else None
            dettes.append({
                'id': p.id,
                'reference': p.reference,
                'montant': float(p.montant),
                'date': p.date.isoformat() if p.date else None,
                'commande_numero': commande.numero if commande else '',
                'commande_id': commande.id if commande else None,
            })

        return JsonResponse({'success': True, 'dettes': dettes, 'total': float(sum(d['montant'] for d in dettes))})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
def api_caisses_disponibles(request):
    """API caisses accessibles à l'utilisateur."""
    caisses = PaiementEngine.get_caisses_disponibles(request.user)
    return JsonResponse({'success': True, 'caisses': caisses})


@login_required
def api_recherche_clients(request):
    """API recherche de clients pour le dialog paiement."""
    from apps.clients.models import Client
    from django.db.models import Q

    search = request.GET.get('search', '')
    qs = Client.objects.all()
    if search:
        qs = qs.filter(Q(nom__icontains=search) | Q(telephone__icontains=search))
    qs = qs[:20]

    result = []
    for c in qs:
        try:
            solde = PaiementEngine.get_solde_client(c.id)
            solde_val = solde['solde']
        except Exception:
            solde_val = 0

        result.append({
            'id': c.id,
            'nom': c.nom_complet,
            'telephone': c.telephone,
            'solde': solde_val,
        })

    return JsonResponse({'success': True, 'clients': result})


@login_required
def recu_paiement(request, paiement_id):
    """Affiche le reçu de caisse format 80mm pour un paiement."""
    paiement = get_object_or_404(Paiement, id=paiement_id)

    # Résoudre les infos source
    source_info = {}
    if paiement.objet:
        obj = paiement.objet
        from apps.facturation.models import FactureModel
        if isinstance(obj, FactureModel):
            source_info = {
                'type': 'facture',
                'numero': obj.numero,
                'client_nom': obj.client_nom,
                'lignes': [],
            }
            for ligne in obj.lignes.all():
                source_info['lignes'].append({
                    'description': ligne.description,
                    'quantite': float(ligne.quantite),
                    'prix_unitaire': float(ligne.prix_unitaire),
                    'total_ttc': float(ligne.total_ttc),
                })
        else:
            from apps.pos.models import Commande
            if isinstance(obj, Commande):
                source_info = {
                    'type': 'commande',
                    'numero': obj.numero,
                    'client_nom': obj.client.nom if obj.client else 'Anonyme',
                    'lignes': [],
                }
                for ligne in obj.lignes.all():
                    source_info['lignes'].append({
                        'description': ligne.article.nom,
                        'quantite': float(ligne.quantite),
                        'prix_unitaire': float(ligne.prix_unitaire),
                        'total_ttc': float(ligne.total),
                    })
            else:
                source_info = {
                    'type': 'client',
                    'numero': '',
                    'client_nom': getattr(obj, 'nom', ''),
                    'lignes': [],
                }

    context = {
        'paiement': paiement,
        'source_info': source_info,
        'societe': {
            'nom': 'Résidence DAMOU',
            'slogan': '',
            'adresse': '',
            'telephone': '',
        }
    }
    return render(request, 'paiements/recu.html', context)

    
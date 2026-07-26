from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST
from django.db import transaction
from django.utils import timezone
from decimal import Decimal
import json
import uuid

from ..models import Inventaire, LigneInventaire, Produit, StockEntrepot, Entrepot
from ..services import MouvementStockService, InventaireService


@login_required
def liste_inventaires(request):
    """Liste des sessions d'inventaire"""
    inventaires = Inventaire.objects.all().order_by('-date_debut')

    search = request.GET.get('search')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    statut = request.GET.get('statut')
    entrepot_id = request.GET.get('entrepot_id')

    if search:
        inventaires = inventaires.filter(code__icontains=search)
    if date_debut:
        inventaires = inventaires.filter(date_debut__date__gte=date_debut)
    if date_fin:
        inventaires = inventaires.filter(date_debut__date__lte=date_fin)
    if statut:
        inventaires = inventaires.filter(statut=statut)
    if entrepot_id:
        inventaires = inventaires.filter(entrepot_id=entrepot_id)

    context = {
        'inventaires': inventaires,
        'total': inventaires.count(),
        'titre': 'Gestion des inventaires',
        'search': search or '',
        'date_debut': date_debut or '',
        'date_fin': date_fin or '',
        'statut_filtre': statut or '',
        'entrepot_filtre': entrepot_id or '',
        'entrepots': Entrepot.objects.filter(actif=True),
        'statuts': Inventaire.STATUS_CHOICES,
    }
    return render(request, 'stock/inventaire/liste.html', context)


@login_required
def creer_inventaire(request, entrepot_id=None):
    """Créer une nouvelle session d'inventaire via InventaireService."""
    entrepots = Entrepot.objects.filter(actif=True)

    if request.method == 'POST':
        entrepot_id = request.POST.get('entrepot_id')
        entrepot = get_object_or_404(Entrepot, id=entrepot_id)

        try:
            inventaire = InventaireService.creer(
                entrepot=entrepot,
                notes=request.POST.get('notes', ''),
                realise_par=request.user.username,
            )
            messages.success(request, f"Inventaire {inventaire.code} créé")
            return redirect('stock:detail_inventaire', inventaire_id=inventaire.id)
        except Exception as e:
            messages.error(request, str(e))
            return redirect('stock:liste_inventaires')

    # Vérifier les verrous pour chaque entrepôt
    entrepot_data = []
    for e in entrepots:
        deja_init = Inventaire.objects.filter(entrepot=e, statut='VALIDE').exists()
        en_cours = Inventaire.objects.filter(entrepot=e, statut='EN_COURS').exists()
        entrepot_data.append({
            'id': e.id, 'nom': e.nom, 'code': e.code,
            'type_entrepot': e.type_entrepot,
            'est_initialise': deja_init,
            'est_verrouille': en_cours,
        })

    context = {
        'entrepots': entrepots,
        'entrepot_data': entrepot_data,
        'titre': 'Nouvel inventaire',
    }
    return render(request, 'stock/inventaire/creer.html', context)


@login_required
def detail_inventaire(request, inventaire_id):
    """Détail d'un inventaire"""
    inventaire = get_object_or_404(Inventaire, id=inventaire_id)
    lignes = inventaire.lignes.all().select_related('produit', 'produit__categorie')

    est_premier = inventaire.statut != 'VALIDE' and not Inventaire.objects.filter(
        entrepot=inventaire.entrepot, statut='VALIDE'
    ).exists()

    # Valorisation
    valeur_theorique = 0
    valeur_reelle = 0
    for l in lignes:
        pu = float(l.prix_unitaire or l.produit.prix_achat or 0)
        valeur_theorique += float(l.quantite_theorique) * pu
        valeur_reelle += float(l.quantite_reelle) * pu

    context = {
        'inventaire': inventaire,
        'lignes': lignes,
        'est_premier': est_premier,
        'est_valide': inventaire.statut == 'VALIDE',
        'valeur_theorique': valeur_theorique,
        'valeur_reelle': valeur_reelle,
        'valeur_ecart': valeur_reelle - valeur_theorique,
        'titre': f'Inventaire {inventaire.code}',
    }
    return render(request, 'stock/inventaire/detail.html', context)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_mettre_a_jour_ligne(request, ligne_id):
    """API pour mettre à jour la quantité réelle d'une ligne d'inventaire"""
    try:
        data = json.loads(request.body)
        ligne = get_object_or_404(LigneInventaire, id=ligne_id)
        ligne = InventaireService.mettre_a_jour_ligne(
            ligne,
            quantite_reelle=data.get('quantite_reelle', 0),
            prix_unitaire=data.get('prix_unitaire'),
        )
        return JsonResponse({
            'success': True,
            'ecart': float(ligne.ecart),
            'quantite_reelle': float(ligne.quantite_reelle),
            'quantite_theorique': float(ligne.quantite_theorique),
            'prix_unitaire': float(ligne.prix_unitaire),
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_http_methods(["GET"])
def api_lignes_inventaire(request, inventaire_id):
    """API pour récupérer toutes les lignes d'un inventaire (GET)"""
    inventaire = get_object_or_404(Inventaire, id=inventaire_id)
    lignes = inventaire.lignes.all()
    data = []
    for l in lignes:
        data.append({
            'id': l.id,
            'produit_id': l.produit_id,
            'produit_nom': l.produit.nom,
            'quantite_theorique': float(l.quantite_theorique),
            'quantite_reelle': float(l.quantite_reelle),
            'prix_unitaire': float(l.prix_unitaire),
            'ecart': float(l.ecart),
        })
    return JsonResponse({'success': True, 'lignes': data})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_valider_inventaire(request, inventaire_id):
    """Valide un inventaire : ajuste les stocks via InventaireService."""
    try:
        inventaire = get_object_or_404(Inventaire, id=inventaire_id)
        ajustements = InventaireService.valider(inventaire, user=request.user)
        return JsonResponse({
            'success': True,
            'message': f'Inventaire validé — {len(ajustements)} produit(s) traités',
            'ajustements': ajustements,
        })
    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def supprimer_inventaire(request, inventaire_id):
    """Supprimer un inventaire non validé"""
    inventaire = get_object_or_404(Inventaire, id=inventaire_id)
    try:
        InventaireService.supprimer(inventaire)
        messages.success(request, f"Inventaire {inventaire.code} supprimé.")
    except Exception as e:
        messages.error(request, str(e))
        return redirect('stock:detail_inventaire', inventaire_id=inventaire.id)
    return redirect('stock:liste_inventaires')

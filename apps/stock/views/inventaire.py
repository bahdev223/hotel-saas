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
from ..services import MouvementStockService
from ..services.stock_compta_service import StockComptaService


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
    """Créer une nouvelle session d'inventaire"""
    entrepots = Entrepot.objects.filter(actif=True)

    if request.method == 'POST':
        entrepot_id = request.POST.get('entrepot_id')
        entrepot = get_object_or_404(Entrepot, id=entrepot_id)

        with transaction.atomic():
            if Inventaire.objects.filter(entrepot=entrepot, statut='EN_COURS').exists():
                messages.error(request, "Un inventaire est déjà en cours pour cet entrepôt.")
                return redirect('stock:liste_inventaires')

            deja_initialise = Inventaire.objects.filter(entrepot=entrepot, statut='VALIDE').exists()

            code = f"INV-{uuid.uuid4().hex[:8].upper()}"

            inventaire = Inventaire.objects.create(
                code=code,
                entrepot=entrepot,
                statut='EN_COURS',
                realise_par=request.user.username,
                notes=request.POST.get('notes', '')
            )

            stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit')

            if not deja_initialise:
                for stock in stocks:
                    LigneInventaire.objects.create(
                        inventaire=inventaire,
                        produit=stock.produit,
                        quantite_theorique=0,
                        quantite_reelle=0,
                        prix_unitaire=stock.produit.prix_achat or 0,
                    )
            else:
                for stock in stocks:
                    LigneInventaire.objects.create(
                        inventaire=inventaire,
                        produit=stock.produit,
                        quantite_theorique=stock.quantite,
                        quantite_reelle=stock.quantite,
                        prix_unitaire=stock.produit.prix_achat or 0,
                    )

            messages.success(request, f"Inventaire {inventaire.code} créé")
            return redirect('stock:detail_inventaire', inventaire_id=inventaire.id)

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
    """API pour mettre à jour la quantité réelle et le prix unitaire d'une ligne"""
    try:
        data = json.loads(request.body)
        quantite_reelle = Decimal(str(data.get('quantite_reelle', 0)))
        if quantite_reelle < 0:
            return JsonResponse({'success': False, 'error': 'La quantité réelle ne peut pas être négative'})
        prix_unitaire = data.get('prix_unitaire')

        ligne = get_object_or_404(LigneInventaire, id=ligne_id)
        ligne.quantite_reelle = quantite_reelle
        if prix_unitaire is not None:
            ligne.prix_unitaire = Decimal(str(prix_unitaire))
        ligne.save()

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
    """Valider l'inventaire via le moteur de mouvements unique"""
    try:
        inventaire = get_object_or_404(Inventaire, id=inventaire_id)
        Inventaire.objects.select_for_update().get(id=inventaire.id)

        if inventaire.statut == 'VALIDE':
            return JsonResponse({'success': False, 'error': 'Inventaire déjà validé'})

        est_premier = not Inventaire.objects.filter(
            entrepot=inventaire.entrepot, statut='VALIDE'
        ).exclude(id=inventaire.id).exists()

        ajustements = []

        for ligne in inventaire.lignes.all().select_related('produit'):
            try:
                stock = StockEntrepot.objects.select_for_update().get(
                    entrepot=inventaire.entrepot, produit=ligne.produit
                )
            except StockEntrepot.DoesNotExist:
                stock = StockEntrepot.objects.create(
                    entrepot=inventaire.entrepot, produit=ligne.produit, quantite=0
                )
                stock = StockEntrepot.objects.select_for_update().get(pk=stock.pk)

            ancienne_quantite = stock.quantite
            nouvelle_quantite = ligne.quantite_reelle
            diff = nouvelle_quantite - ancienne_quantite
            valeur = ligne.prix_unitaire or ligne.produit.prix_achat or Decimal('0')

            if diff > 0:
                if est_premier:
                    MouvementStockService.initialiser_stock(
                        produit=ligne.produit, entrepot=inventaire.entrepot,
                        quantite=diff, utilisateur=request.user.username,
                        valeur_unitaire=valeur, reference=inventaire.code,
                        raison="Stock initial"
                    )
                else:
                    MouvementStockService.entree_stock(
                        produit=ligne.produit, entrepot=inventaire.entrepot,
                        quantite=diff, utilisateur=request.user.username,
                        motif='inventaire', valeur_unitaire=valeur,
                        reference=inventaire.code, raison="Correction inventaire"
                    )
            elif diff < 0:
                MouvementStockService.sortie_stock(
                    produit=ligne.produit, entrepot=inventaire.entrepot,
                    quantite=abs(diff), utilisateur=request.user.username,
                    motif='inventaire', valeur_unitaire=valeur,
                    reference=inventaire.code, raison="Correction inventaire"
                )

            # Mettre à jour le prix d'achat uniquement pour un stock initial
            if est_premier and ligne.prix_unitaire and ligne.prix_unitaire > 0:
                produit = Produit.objects.get(id=ligne.produit.id)
                produit.prix_achat = ligne.prix_unitaire
                produit.save()

            ajustements.append({
                'produit': ligne.produit.nom,
                'avant': float(ancienne_quantite),
                'apres': float(nouvelle_quantite),
                'diff': float(diff),
            })

        inventaire.statut = 'VALIDE'
        inventaire.date_fin = timezone.now()
        inventaire.save()

        return JsonResponse({
            'success': True,
            'message': f'Inventaire validé — {len(ajustements)} produit(s) traités',
            'ajustements': ajustements,
            'est_premier': est_premier,
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)}, status=400)


@login_required
@require_POST
def supprimer_inventaire(request, inventaire_id):
    """Supprimer un inventaire non validé"""
    inventaire = get_object_or_404(Inventaire, id=inventaire_id)

    if inventaire.statut == 'VALIDE':
        messages.error(request, "Impossible de supprimer un inventaire validé.")
        return redirect('stock:detail_inventaire', inventaire_id=inventaire.id)

    inventaire.delete()
    messages.success(request, f"Inventaire {inventaire.code} supprimé.")
    return redirect('stock:liste_inventaires')

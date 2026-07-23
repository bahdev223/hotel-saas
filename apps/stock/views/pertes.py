from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db import transaction
from decimal import Decimal
from ..constants import ALLOWED_STOCK_GROUPS


@login_required
def liste_pertes(request):
    """Page liste des pertes."""
    from ..models.mouvement import MouvementStock
    from apps.stock.models import Produit, Entrepot
    pertes = MouvementStock.objects.filter(
        type_mouvement='SORTIE', motif='perte'
    ).select_related('produit', 'entrepot_source').order_by('-date_mouvement')[:200]
    return render(request, 'stock/pertes.html', {
        'pertes': pertes,
        'produits': Produit.objects.filter(actif=True).order_by('nom'),
        'entrepots': Entrepot.objects.filter(actif=True).order_by('nom'),
    })


@login_required
@require_http_methods(["POST"])
def api_declarer_perte(request):
    """Déclarer une perte de stock (périmé, cassé, vol, etc.)."""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        return JsonResponse({'success': False, 'error': 'Accès refusé'}, status=403)
    import json
    from ..services.mouvement_service import MouvementStockService
    from apps.stock.models import Produit, Entrepot
    try:
        data = json.loads(request.body)
        produit_id = data.get('produit_id')
        entrepot_id = data.get('entrepot_id')
        quantite = data.get('quantite')
        motif = data.get('motif', 'Perte')
        notes = data.get('notes', '')

        if not all([produit_id, entrepot_id, quantite]):
            return JsonResponse({'success': False, 'error': 'Champs obligatoires manquants'})

        quantite = Decimal(str(quantite))
        if quantite <= 0:
            return JsonResponse({'success': False, 'error': 'Quantité doit être > 0'})

        produit = Produit.objects.filter(id=produit_id).first()
        entrepot = Entrepot.objects.filter(id=entrepot_id).first()
        if not produit or not entrepot:
            return JsonResponse({'success': False, 'error': 'Produit ou entrepôt introuvable'})

        MouvementStockService.sortie_stock(
            produit=produit, entrepot=entrepot, quantite=quantite,
            utilisateur=request.user, raison=f"Perte: {motif} - {notes}" if notes else f"Perte: {motif}",
            motif='perte',
        )

        return JsonResponse({'success': True, 'message': f'Perte de {quantite} {produit.unite_base} enregistrée'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

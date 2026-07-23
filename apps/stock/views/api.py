# apps/stock/views/api.py
import json

from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods

from decimal import Decimal
from django.core.paginator import Paginator
from django.db import models
from django.db.models import Sum, Q, F, OuterRef, Subquery, Value, Count
from django.db.models.functions import Coalesce
from ..models import Produit, CategorieProduit, Entrepot, StockEntrepot, SousUnite, Domaine, MouvementStock
from ..services.transfert_service import TransfertService
from ..services import MouvementStockService
from apps.authentication.groups import PATRON, MANAGER, STOCK, BAR, RESTAURANT, CAISSIER

ALLOWED_STOCK_GROUPS = [PATRON, MANAGER, STOCK, BAR, RESTAURANT, CAISSIER]

@login_required
@require_http_methods(["GET"])
def api_produit_stock_converti(request, produit_id):
    """API pour obtenir le stock converti d'un produit"""
    try:
        produit = Produit.objects.get(id=produit_id)
        quantite = int(request.GET.get('quantite', 0))
        
        # Stock converti avec la quantitÃ© donnÃ©e
        if not produit.sous_unites.exists():
            stock_converti = f"{quantite} {produit.unite_base}"
        else:
            result = []
            reste = quantite
            sous_unites_triees = produit.sous_unites.filter(actif=True).order_by('-facteur')
            
            for su in sous_unites_triees:
                facteur = int(su.facteur)
                if facteur > 0 and reste >= facteur:
                    nb = reste // facteur
                    result.append(f"{nb} {su.nom}")
                    reste = reste % facteur
            
            if reste > 0 or not result:
                result.append(f"{reste} {produit.unite_base}")
            stock_converti = ", ".join(result)
        
        return JsonResponse({
            'success': True,
            'stock_converti': stock_converti,
            'quantite_base': quantite,
            'unite_base': produit.unite_base
        })
        
    except Produit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Produit non trouvÃ©'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    
# apps/stock/views/api.py
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.shortcuts import get_object_or_404
from ..models import Produit


@login_required
@require_http_methods(["GET"])
def api_recherche_code_barre(request):
    """Rechercher un produit par code-barres (pour scanner)"""
    code_barre = request.GET.get('code_barre')
    
    if not code_barre:
        return JsonResponse({'success': False, 'error': 'Code-barres requis'})
    
    try:
        produit = Produit.objects.get(code_barre=code_barre, actif=True)
        
        # RÃ©cupÃ©rer stock dans l'entrepÃ´t CENTRAL
        from ..models import Entrepot, StockEntrepot
        central = Entrepot.objects.get(type_entrepot='CENTRAL')
        stock = StockEntrepot.objects.filter(entrepot=central, produit=produit).first()
        quantite = stock.quantite if stock else 0
        
        return JsonResponse({
            'success': True,
            'produit': {
                'id': produit.id,
                'code': produit.code,
                'code_barre': produit.code_barre,
                'nom': produit.nom,
                'prix_vente': float(produit.prix_vente),
                'prix_achat': float(produit.prix_achat),
                'unite_base': produit.unite_base,
                'quantite_stock': float(quantite),
                'image': produit.image.url if produit.image else None,
                'stock_converti': produit.stock_converti
            }
        })
        
    except Produit.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Produit non trouvÃ©'})
    
    
# apps/stock/views/api.py
@login_required
@csrf_exempt
def api_modifier_image_produit(request, produit_id):
    """Modifier l'image d'un produit"""
    if request.method == 'POST':
        try:
            produit = get_object_or_404(Produit, id=produit_id)
            if 'image' in request.FILES:
                # Supprimer l'ancienne image
                if produit.image:
                    produit.image.delete()
                produit.image = request.FILES['image']
                produit.save()
                return JsonResponse({'success': True})
            return JsonResponse({'success': False, 'error': 'Aucune image fournie'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
@csrf_exempt
def api_supprimer_image_produit(request, produit_id):
    """Supprimer l'image d'un produit"""
    if request.method == 'POST':
        try:
            produit = get_object_or_404(Produit, id=produit_id)
            if produit.image:
                produit.image.delete()
                produit.image = None
                produit.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@login_required
@csrf_exempt
def api_supprimer_produit(request, produit_id):
    """Supprimer (soft delete) un produit"""
    if request.method == 'POST':
        try:
            produit = get_object_or_404(Produit, id=produit_id)
            produit.actif = False
            produit.save()
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})

@login_required
@require_http_methods(["GET"])
def api_produit_infos(request, produit_id):
    """
    RÃ©cupÃ©rer les infos d'un produit avec ses sous-unitÃ©s
    UtilisÃ© par le modal de transfert
    """
    try:
        produit = Produit.objects.get(id=produit_id, actif=True)
        
        # RÃ©cupÃ©rer la quantitÃ© dans l'entrepÃ´t CENTRAL
        central = Entrepot.objects.get(type_entrepot='CENTRAL')
        stock = StockEntrepot.objects.filter(entrepot=central, produit=produit).first()
        quantite_stock = float(stock.quantite) if stock else 0
        
        # Liste des sous-unitÃ©s
        sous_unites = []
        for su in produit.sous_unites.filter(actif=True):
            sous_unites.append({
                'id': su.id,
                'nom': su.nom,
                'facteur': float(su.facteur),
                'prix': float(su.prix) if su.prix else None
            })
        
        return JsonResponse({
            'success': True,
            'produit': {
                'id': produit.id,
                'code': produit.code,
                'nom': produit.nom,
                'description': produit.description or '',
                'categorie': produit.categorie.nom if produit.categorie else None,
                'categorie_id': produit.categorie_id,
                'categorie_nom': produit.categorie.nom if produit.categorie else '',
                'domaine': produit.domaine.nom if produit.domaine else None,
                'domaine_id': produit.domaine_id,
                'domaine_nom': produit.domaine.nom if produit.domaine else '',
                'type_article': produit.type_article,
                'type_article_display': produit.get_type_article_display(),
                'est_vendable': produit.est_vendable,
                'unite_base': produit.unite_base,
                'quantite_stock': quantite_stock,
                'prix_achat': float(produit.prix_achat) if produit.prix_achat else 0,
                'prix_vente': float(produit.prix_vente) if produit.prix_vente else 0,
                'seuil_alerte': float(produit.seuil_alerte) if produit.seuil_alerte else 0,
                'actif': produit.actif,
                'image_url': produit.image.url if produit.image else None,
                'sous_unites': sous_unites
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def api_produit_stock(request, produit_id):
    """
    RÃ©cupÃ©rer le stock d'un produit dans l'entrepÃ´t CENTRAL
    """
    try:
        produit = Produit.objects.get(id=produit_id)
        central = Entrepot.objects.get(type_entrepot='CENTRAL')
        stock = StockEntrepot.objects.filter(entrepot=central, produit=produit).first()
        quantite = float(stock.quantite) if stock else 0
        
        return JsonResponse({
            'success': True,
            'quantite': quantite,
            'unite_base': produit.unite_base
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_stock_by_entrepot_produit(request, entrepot_id, produit_id):
    """API pour rÃ©cupÃ©rer le stock d'un produit dans un entrepÃ´t spÃ©cifique"""
    try:
        stock = StockEntrepot.objects.get(entrepot_id=entrepot_id, produit_id=produit_id)
        return JsonResponse({
            'success': True,
            'quantite': float(stock.quantite),
            'unite': stock.produit.unite_base
        })
    except StockEntrepot.DoesNotExist:
        # Retourner 0 au lieu d'une erreur 404
        return JsonResponse({'success': True, 'quantite': 0})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


# apps/stock/views/api.py

@csrf_exempt
@login_required
def api_ajouter_entrepot(request):
    """API pour ajouter un entrepÃ´t via modal"""
    
    # VÃ©rifier les droits
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
        return JsonResponse({'success': False, 'error': 'â›” AccÃ¨s refusÃ©'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body)
        
        code = data.get('code', '').strip().upper()
        nom = data.get('nom', '').strip()
        type_entrepot = data.get('type_entrepot', '')
        
        if not code:
            return JsonResponse({'success': False, 'error': 'Code requis'})
        if not nom:
            return JsonResponse({'success': False, 'error': 'Nom requis'})
        if not type_entrepot:
            return JsonResponse({'success': False, 'error': 'Type requis'})
        
        if Entrepot.objects.filter(code=code).exists():
            return JsonResponse({'success': False, 'error': f'Le code {code} existe dÃ©jÃ '})
        
        entrepot = Entrepot.objects.create(
            code=code,
            nom=nom,
            type_entrepot=type_entrepot,
            actif=True
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'EntrepÃ´t {entrepot.nom} crÃ©Ã©',
            'entrepot': {
                'id': entrepot.id,
                'code': entrepot.code,
                'nom': entrepot.nom,
                'type': entrepot.get_type_entrepot_display()
            }
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    

@csrf_exempt
@login_required
def api_ajouter_entree(request):
    """API ultra simple pour ajouter une entrÃ©e stock"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    
    try:
        data = json.loads(request.body)
        
        # GÃ©nÃ©rer une rÃ©fÃ©rence
        from datetime import datetime
        reference = f"ENT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        # RÃ©cupÃ©rer l'entrepÃ´t central
        central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
        if not central:
            central = Entrepot.objects.create(
                code='STK001',
                nom='STOCK CENTRAL',
                type_entrepot='CENTRAL',
                actif=True
            )
        
        # Pour chaque ligne
        for ligne in data.get('lignes', []):
            produit_id = ligne.get('produit_id')
            quantite = Decimal(str(ligne.get('quantite', 0)))
            prix = Decimal(str(ligne.get('prix', 0)))
            
            if not produit_id or quantite <= 0:
                continue
            
            # Entrée stock via le moteur unique
            MouvementStockService.entree_stock(
                produit=Produit.objects.get(id=produit_id),
                entrepot=central,
                quantite=quantite,
                utilisateur=request.user.username,
                motif='achat',
                valeur_unitaire=prix,
                reference=reference,
                raison="Entrée stock"
            )
            
            # Mettre à jour le prix d'achat si fourni
            if prix > 0:
                produit = Produit.objects.get(id=produit_id)
                produit.prix_achat = prix
                produit.save()
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_liste_entrees(request):
    """API pour lister les entrÃ©es"""
    mouvements = MouvementStock.objects.filter(
        type_mouvement='ENTREE', motif='achat'
    ).order_by('-date_mouvement')[:100]
    
    entrees = []
    for m in mouvements:
        entrees.append({
            'id': m.id,
            'date': m.date_mouvement,
            'reference': m.reference,
            'fournisseur': 'N/A',
            'produits_count': 1,
            'produits_liste': m.produit.nom
        })
    
    return JsonResponse({'success': True, 'entrees': entrees})


@login_required
@csrf_exempt
def api_modifier_produit(request, produit_id):
    """API pour modifier un produit"""
    if request.user.is_authenticated:
        user_groups = request.user.groups.values_list('name', flat=True)
        if not any(g in ALLOWED_STOCK_GROUPS for g in user_groups):
            return JsonResponse({'success': False, 'error': 'AccÃ¨s refusÃ©'}, status=403)
    else:
        return JsonResponse({'success': False, 'error': 'Non authentifiÃ©'}, status=401)

    if request.method == 'POST':
        try:
            produit = Produit.objects.get(id=produit_id)
            if request.content_type and 'multipart' in request.content_type:
                produit.nom = request.POST.get('nom', produit.nom)
                produit.categorie_id = request.POST.get('categorie') or produit.categorie_id
                produit.unite_base = request.POST.get('unite_base', produit.unite_base)
                produit.prix_achat = Decimal(request.POST.get('prix_achat', produit.prix_achat or 0))
                produit.prix_vente = Decimal(request.POST.get('prix_vente', produit.prix_vente or 0))
                produit.seuil_alerte = Decimal(request.POST.get('seuil_alerte', produit.seuil_alerte or 0))
                produit.description = request.POST.get('description', produit.description or '')
                if 'image' in request.FILES:
                    if produit.image:
                        produit.image.delete()
                    produit.image = request.FILES['image']
                produit.save()

                sous_unites_data = json.loads(request.POST.get('sous_unites', '[]'))
                produit.sous_unites.filter(actif=True).update(actif=False)
                for su in sous_unites_data:
                    SousUnite.objects.create(
                        produit=produit, nom=su.get('nom'),
                        facteur=Decimal(su.get('facteur', 1)),
                        prix=Decimal(su.get('prix')) if su.get('prix') else None,
                        actif=True
                    )
            else:
                data = json.loads(request.body)
                for field in ['nom', 'unite_base', 'description']:
                    if field in data:
                        setattr(produit, field, data[field])
                for field in ['prix_achat', 'prix_vente', 'seuil_alerte']:
                    if field in data:
                        setattr(produit, field, Decimal(str(data[field])))
                if 'categorie' in data:
                    produit.categorie_id = data['categorie'] or None
                produit.save()

            return JsonResponse({'success': True})
        except Produit.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Produit non trouvé'})
        except Exception as e:
            import traceback; traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


# ========== SPA API ENDPOINTS ==========

@login_required
@require_http_methods(["GET"])
def api_liste_produits(request):
    """API liste des produits (JSON) pour le catalogue SPA"""
    central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
    produits_qs = Produit.objects.filter(actif=True).order_by('nom')

    if central:
        stock_sub = StockEntrepot.objects.filter(entrepot=central, produit=OuterRef('pk')).values('quantite')[:1]
        produits_qs = produits_qs.annotate(
            stock_central=Coalesce(Subquery(stock_sub), Value(0, output_field=models.DecimalField(max_digits=10, decimal_places=2)))
        )

    search = request.GET.get('search')
    if search:
        produits_qs = produits_qs.filter(Q(nom__icontains=search) | Q(code__icontains=search))
    type_filter = request.GET.get('type_article')
    if type_filter:
        produits_qs = produits_qs.filter(type_article=type_filter)
    domaine_id = request.GET.get('domaine')
    if domaine_id:
        produits_qs = produits_qs.filter(domaine_id=domaine_id)
    categorie_id = request.GET.get('categorie')
    if categorie_id:
        produits_qs = produits_qs.filter(categorie_id=categorie_id)

    all_flag = request.GET.get('all')
    if all_flag:
        data = [{'id': p.id, 'nom': p.nom, 'code': p.code, 'unite_base': p.unite_base,
                 'prix_achat': float(p.prix_achat or 0), 'prix_vente': float(p.prix_vente or 0),
                 'domaine_id': p.domaine_id, 'domaine_nom': p.domaine.nom if p.domaine else '',
                 'est_vendable': p.est_vendable} for p in produits_qs]
        return JsonResponse({'success': True, 'produits': data})

    paginator = Paginator(produits_qs, 20)
    page = request.GET.get('page', 1)
    produits_page = paginator.get_page(page)

    total_actifs = produits_qs.count()
    rupture = produits_qs.annotate(
        qte=Coalesce(Subquery(StockEntrepot.objects.filter(
            entrepot=central, produit=OuterRef('pk')).values('quantite')[:1]), Value(0, output_field=models.DecimalField(max_digits=10, decimal_places=2)))
    ).filter(qte__lte=0).count() if central else 0

    produits_data = []
    for p in produits_page:
        qte = float(getattr(p, 'stock_central', 0) or 0)
        produits_data.append({
            'id': p.id, 'nom': p.nom, 'code': p.code,
            'categorie_nom': p.categorie.nom if p.categorie else '',
            'domaine_nom': p.domaine.nom if p.domaine else '',
            'type_article_display': p.get_type_article_display(),
            'unite_base': p.unite_base,
            'prix_achat': float(p.prix_achat or 0),
            'prix_vente': float(p.prix_vente or 0),
            'quantite_stock': qte,
            'seuil_alerte': float(p.seuil_alerte or 0),
            'image_url': p.image.url if p.image else None,
        })

    return JsonResponse({
        'success': True, 'produits': produits_data,
        'total_pages': paginator.num_pages, 'page': int(page),
        'stats': {'total': total_actifs, 'actifs': total_actifs, 'rupture': rupture}
    })


@login_required
@require_http_methods(["GET"])
def api_liste_mouvements(request):
    """API liste des mouvements pour la SPA"""
    qs = MouvementStock.objects.select_related('produit', 'entrepot_source', 'entrepot_dest').order_by('-date_mouvement')

    type_mvt = request.GET.get('type')
    motif = request.GET.get('motif')
    entrepot = request.GET.get('entrepot')
    produit = request.GET.get('produit')
    periode = request.GET.get('periode', '')

    from datetime import date, timedelta
    today = date.today()
    if periode == 'jour':
        qs = qs.filter(date_mouvement__date=today)
    elif periode == 'semaine':
        debut_semaine = today - timedelta(days=today.weekday())
        qs = qs.filter(date_mouvement__date__gte=debut_semaine)
    elif periode == 'mois':
        debut_mois = today.replace(day=1)
        qs = qs.filter(date_mouvement__date__gte=debut_mois)

    if type_mvt:
        qs = qs.filter(type_mouvement=type_mvt)
    if motif:
        qs = qs.filter(motif=motif)
    if entrepot:
        qs = qs.filter(
            Q(entrepot_source=entrepot) | Q(entrepot_dest=entrepot)
        )
    if produit:
        qs = qs.filter(produit_id=produit)

    data = []
    for m in qs[:200]:
        data.append({
            'id': m.id, 'date': m.date_mouvement.strftime('%d/%m %H:%M') if m.date_mouvement else '',
            'produit_nom': m.produit.nom if m.produit else '',
            'type_mouvement': m.type_mouvement,
            'motif': m.motif,
            'motif_display': m.get_motif_display(),
            'quantite': float(m.quantite),
            'unite_base': m.produit.unite_base if m.produit else '',
            'source_nom': m.entrepot_source.nom if m.entrepot_source else '',
            'dest_nom': m.entrepot_dest.nom if m.entrepot_dest else '',
            'reference': m.reference or '',
        })
    return JsonResponse({'success': True, 'mouvements': data})


@login_required
@require_http_methods(["GET"])
def api_liste_motifs(request):
    """Retourne les motifs distincts des mouvements de stock."""
    from django.db.models import Count
    motifs = MouvementStock.objects.values('motif').annotate(
        count=Count('id')
    ).order_by('-count')
    data = [{'code': m['motif'], 'label': dict(MouvementStock.MOTIF_CHOICES).get(m['motif'], m['motif']), 'count': m['count']} for m in motifs]
    return JsonResponse({'success': True, 'motifs': data})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_ajouter_sortie(request):
    """API ajouter une sortie de stock"""
    try:
        data = json.loads(request.body)
        produit_id = data.get('produit')
        quantite = Decimal(str(data.get('quantite', 0)))
        motif = data.get('motif', 'perte')
        reference = data.get('reference', '')
        raison = data.get('raison', '')

        central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
        if not central:
            return JsonResponse({'success': False, 'error': 'Entrepot central non trouve'})

        produit = Produit.objects.get(id=produit_id)

        MouvementStockService.sortie_stock(
            produit=produit, entrepot=central,
            quantite=quantite, utilisateur=request.user.username,
            motif=motif, valeur_unitaire=float(produit.prix_achat or 0),
            reference=reference, raison=raison or f"Sortie {motif}"
        )
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def api_liste_transferts(request):
    """API liste des transferts pour la SPA"""
    transferts = MouvementStock.objects.filter(
        motif='reapprovisionnement'
    ).select_related('produit', 'entrepot_source', 'entrepot_dest').order_by('-date_mouvement')[:100]
    data = []
    for t in transferts:
        data.append({
            'id': t.id, 'date': t.date_mouvement.strftime('%d/%m %H:%M') if t.date_mouvement else '',
            'produit_nom': t.produit.nom if t.produit else '',
            'quantite': float(t.quantite),
            'source_nom': t.entrepot_source.nom if t.entrepot_source else '-',
            'dest_nom': t.entrepot_dest.nom if t.entrepot_dest else '-',
            'type': t.type_mouvement,
            'reference': t.reference or '',
        })
    return JsonResponse({'success': True, 'transferts': data})


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_effectuer_transfert(request):
    """API effectuer un transfert entre entrepots"""
    try:
        data = json.loads(request.body)
        mouvement = TransfertService.transfert_entre_entrepots(
            produit_id=data['produit'],
            quantite=data['quantite'],
            entrepot_source_id=data['source'],
            entrepot_dest_id=data['dest'],
            utilisateur=request.user.username,
            reference=data.get('reference', ''),
        )
        return JsonResponse({'success': True, 'mouvement_id': mouvement.id})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
@require_http_methods(["GET"])
def api_liste_entrepots(request):
    """API liste des entrepots pour la SPA"""
    from django.db.models import Count
    entrepots = Entrepot.objects.filter(actif=True).annotate(
        produits_count=Coalesce(
            Subquery(StockEntrepot.objects.filter(entrepot=OuterRef('pk')).values('entrepot').annotate(
                cnt=Count('produit')).values('cnt')[:1]), Value(0)
        )
    ).order_by('nom')
    data = []
    for e in entrepots:
        data.append({
            'id': e.id, 'nom': e.nom, 'code': e.code,
            'type_entrepot': e.type_entrepot, 'type_display': e.get_type_entrepot_display(),
            'actif': e.actif, 'produits_count': e.produits_count,
        })
    return JsonResponse({'success': True, 'entrepots': data})


@login_required
@require_http_methods(["GET"])
def api_detail_entrepot_stocks(request, entrepot_id):
    """API detail d'un entrepot avec ses stocks (filtrable par domaine/categorie/recherche)"""
    entrepot = get_object_or_404(Entrepot, id=entrepot_id)
    stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit__domaine', 'produit__categorie')

    domaine_id = request.GET.get('domaine')
    categorie_id = request.GET.get('categorie')
    search = request.GET.get('search', '').strip()

    if domaine_id:
        stocks = stocks.filter(produit__domaine_id=domaine_id)
    if categorie_id:
        stocks = stocks.filter(produit__categorie_id=categorie_id)
    if search:
        stocks = stocks.filter(produit__nom__icontains=search)

    stocks_data = [{
        'produit_id': s.produit.id,
        'produit_nom': s.produit.nom,
        'quantite': float(s.quantite),
        'domaine': s.produit.domaine.nom if s.produit.domaine else None,
        'categorie': s.produit.categorie.nom if s.produit.categorie else None,
    } for s in stocks]

    return JsonResponse({
        'success': True,
        'id': entrepot.id, 'nom': entrepot.nom, 'code': entrepot.code,
        'type_display': entrepot.get_type_entrepot_display(),
        'stocks': stocks_data,
    })


@login_required
@require_http_methods(["GET"])
def api_notifications_stock(request):
    """Retourne les alertes stock bas pour la cloche de notification"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(group in ALLOWED_STOCK_GROUPS for group in user_groups):
        return JsonResponse({"success": True, "count": 0, "items": []})

    stocks = StockEntrepot.objects.values(
        'produit_id', 'produit__nom', 'produit__seuil_alerte'
    ).annotate(total=Sum('quantite'))

    items = []
    for s in stocks:
        total = float(s['total'])
        seuil = float(s['produit__seuil_alerte'])
        if total <= 0:
            items.append({
                "produit_id": s['produit_id'],
                "produit_nom": s['produit__nom'],
                "quantite": total,
                "seuil": seuil,
                "type": "Rupture",
            })
        elif 0 < total <= seuil:
            items.append({
                "produit_id": s['produit_id'],
                "produit_nom": s['produit__nom'],
                "quantite": total,
                "seuil": seuil,
                "type": "Stock bas",
            })

    items.sort(key=lambda x: x['quantite'])

    return JsonResponse({
        "success": True,
        "count": len(items),
        "items": items[:20],
    })


@login_required
@require_http_methods(["GET"])
def api_liste_domaines(request):
    domaines = Domaine.objects.filter(actif=True).order_by('ordre', 'nom')
    data = [{'id': d.id, 'nom': d.nom} for d in domaines]
    return JsonResponse({'success': True, 'domaines': data})


@login_required
@require_http_methods(["GET"])
def api_liste_categories(request):
    categories = CategorieProduit.objects.filter(actif=True).order_by('nom')
    data = [{'id': c.id, 'nom': c.nom} for c in categories]
    return JsonResponse({'success': True, 'categories': data})

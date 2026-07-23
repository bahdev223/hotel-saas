import json
import uuid
from decimal import Decimal
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from apps.stock.models import Produit, CategorieProduit, Domaine, StockEntrepot, Entrepot
from apps.dashboard.services import (
    get_ca_brasserie,
    get_ca_mensuel_par_categorie,
    get_top_produits_par_entrepot,
    get_activites_brasserie,
    get_commandes_en_cours,
)
from apps.authentication.groups import PATRON, MANAGER, BAR, CAISSIER, RAF

ALLOWED_GROUPS = [PATRON, MANAGER, BAR, CAISSIER, RAF]


@login_required
def brasserie_dashboard(request):
    """Tableau de bord Brasserie — CA, stock, top produits, activités."""

    entrepot = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()

    # --- Stock ---
    produits_stock = []
    valeur_stock = 0
    nb_alertes = 0
    nb_ruptures = 0

    if entrepot:
        stocks = StockEntrepot.objects.filter(
            entrepot=entrepot, produit__actif=True, produit__domaine__nom='BRASSERIE',
        ).select_related('produit', 'produit__categorie').order_by('produit__nom')

        for s in stocks:
            qte = float(s.quantite)
            pv = float(s.produit.prix_vente)
            pa = float(s.prix_achat or s.produit.prix_achat or 0)
            seuil = float(s.produit.seuil_alerte)
            alerte = qte <= seuil and qte > 0
            rupture = qte <= 0
            if alerte:
                nb_alertes += 1
            if rupture:
                nb_ruptures += 1
            valeur_stock += qte * pa
            produits_stock.append({
                'code': s.produit.code,
                'nom': s.produit.nom,
                'categorie_nom': s.produit.categorie.nom if s.produit.categorie else '',
                'quantite': qte,
                'prix_vente': pv,
                'prix_achat': pa,
                'seuil': seuil,
                'alerte': alerte,
                'rupture': rupture,
            })

    # --- CA mensuel (brasserie uniquement) ---
    ca_mensuel = get_ca_mensuel_par_categorie()
    ca_brasserie_evolution = [{'date': d['date'], 'ca': d['brasserie']} for d in ca_mensuel]

    # --- Top produits vendus à la brasserie ---
    top_produits = get_top_produits_par_entrepot('BRASSERIE', limit=5)

    # --- Activités brasserie ---
    activites = get_activites_brasserie()

    # --- Commandes en cours (brasserie) ---
    commandes = get_commandes_en_cours()
    commandes_brasserie = commandes['brasserie']

    context = {
        'entrepot': entrepot,
        'produits_stock': produits_stock,
        'nb_produits': len(produits_stock),
        'nb_alertes': nb_alertes,
        'nb_ruptures': nb_ruptures,
        'valeur_stock': valeur_stock,
        'ca_brasserie': get_ca_brasserie(),
        'ca_brasserie_evolution': ca_brasserie_evolution,
        'top_produits': top_produits,
        'activites': activites,
        'commandes_brasserie': commandes_brasserie,
        'domaines': Domaine.objects.filter(actif=True).order_by('ordre', 'nom'),
        'categories_list_json': json.dumps(sorted(set(p['categorie_nom'] for p in produits_stock if p['categorie_nom']))),
    }
    return render(request, 'dashboard/brasserie.html', context)


@login_required
def brasserie_produits(request):
    """Liste des produits disponibles dans l'entrepôt Brasserie"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_GROUPS for g in user_groups):
        messages.error(request, "Acces refuse.")
        return redirect('admin:index')

    entrepot_bar = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()
    produits = []
    if entrepot_bar:
        stocks = StockEntrepot.objects.filter(
            entrepot=entrepot_bar, produit__actif=True, produit__domaine__nom='BRASSERIE'
        ).select_related('produit', 'produit__categorie', 'produit__domaine').order_by('produit__nom')
        for s in stocks:
            p = s.produit
            produits.append({
                'id': p.id,
                'code': p.code,
                'nom': p.nom,
                'description': p.description,
                'categorie_nom': p.categorie.nom if p.categorie else '',
                'domaine_nom': p.domaine.nom if p.domaine else '',
                'image': p.image,
                'prix_vente': p.prix_vente,
                'quantite': float(s.quantite),
                'stock_converti': f"{int(s.quantite)} {p.unite_base}",
                'alerte': 0 < float(s.quantite) <= float(p.seuil_alerte),
                'rupture': float(s.quantite) <= 0,
            })

    categories = CategorieProduit.objects.filter(actif=True)
    categories_list = sorted(set(p['categorie_nom'] for p in produits if p['categorie_nom']))
    domaines_list = sorted(set(p['domaine_nom'] for p in produits if p['domaine_nom']))
    domaines = Domaine.objects.filter(actif=True).order_by('ordre', 'nom')

    context = {
        'produits': produits,
        'categories': categories,
        'categories_list': categories_list,
        'domaines_list': domaines_list,
        'domaines': domaines,
        'entrepot_bar': entrepot_bar,
    }
    return render(request, 'dashboard/brasserie_produits.html', context)


@csrf_exempt
def brasserie_ajouter_api(request):
    """API pour ajouter un produit Brasserie (auto: MARCHANDISE, est_vendable=True)"""
    if request.user.is_authenticated:
        user_groups = request.user.groups.values_list('name', flat=True)
        if not any(g in ALLOWED_GROUPS for g in user_groups):
            return JsonResponse({'success': False, 'error': 'Acces refuse'}, status=403)
    else:
        return JsonResponse({'success': False, 'error': 'Non authentifie'}, status=401)

    if request.method == 'POST':
        try:
            nom = request.POST.get('nom')
            if not nom:
                return JsonResponse({'success': False, 'error': 'Nom requis'})

            code = f"BRD-{uuid.uuid4().hex[:6].upper()}"
            produit = Produit.objects.create(
                code=code,
                nom=nom,
                categorie_id=request.POST.get('categorie') or None,
                type_article='MARCHANDISE',
                est_vendable=True,
                unite_base=request.POST.get('unite_base', 'piece'),
                prix_vente=Decimal(request.POST.get('prix_vente', 0)),
                description=request.POST.get('description', ''),
                image=request.FILES.get('image'),
                actif=True,
            )

            # Ajouter automatiquement dans l'entrepôt Brasserie avec quantité initiale
            quantite_initiale = Decimal(request.POST.get('quantite_initiale', 0))
            entrepot_brasserie = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()
            if entrepot_brasserie:
                StockEntrepot.objects.get_or_create(
                    entrepot=entrepot_brasserie,
                    produit=produit,
                    defaults={'quantite': quantite_initiale}
                )

            return JsonResponse({'success': True, 'produit_id': produit.id, 'code': produit.code})

        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'POST requis'})


@csrf_exempt
def brasserie_modifier_api(request, produit_id):
    """API pour modifier un produit Brasserie"""
    if request.user.is_authenticated:
        user_groups = request.user.groups.values_list('name', flat=True)
        if not any(g in ALLOWED_GROUPS for g in user_groups):
            return JsonResponse({'success': False, 'error': 'Acces refuse'}, status=403)
    else:
        return JsonResponse({'success': False, 'error': 'Non authentifie'}, status=401)

    if request.method == 'POST':
        try:
            produit = get_object_or_404(Produit, id=produit_id)
            produit.nom = request.POST.get('nom', produit.nom)
            produit.categorie_id = request.POST.get('categorie') or produit.categorie_id
            produit.unite_base = request.POST.get('unite_base', produit.unite_base)
            produit.prix_vente = Decimal(request.POST.get('prix_vente', produit.prix_vente or 0))
            produit.description = request.POST.get('description', produit.description or '')
            if 'image' in request.FILES:
                if produit.image:
                    produit.image.delete()
                produit.image = request.FILES['image']
            produit.save()

            # Mise à jour du stock si fourni
            if 'quantite' in request.POST:
                quantite = Decimal(request.POST.get('quantite', 0))
                entrepot_brasserie = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()
                if entrepot_brasserie:
                    stock, _ = StockEntrepot.objects.get_or_create(
                        entrepot=entrepot_brasserie,
                        produit=produit,
                        defaults={'quantite': quantite}
                    )
                    if not _:
                        stock.quantite = quantite
                        stock.save()

            return JsonResponse({'success': True, 'produit_id': produit.id})
        except Exception as e:
            import traceback; traceback.print_exc()
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST requis'})


@csrf_exempt
def brasserie_modifier_stock_api(request, produit_id):
    """API pour modifier le stock d'un produit Brasserie (inline)"""
    if not request.user.is_authenticated:
        return JsonResponse({'success': False, 'error': 'Non authentifie'}, status=401)
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_GROUPS for g in user_groups):
        return JsonResponse({'success': False, 'error': 'Acces refuse'}, status=403)

    if request.method == 'POST':
        try:
            quantite = Decimal(request.POST.get('quantite', 0))
            entrepot = Entrepot.objects.filter(type_entrepot='BRASSERIE', actif=True).first()
            if not entrepot:
                return JsonResponse({'success': False, 'error': 'Entrepot Brasserie introuvable'})
            stock, _ = StockEntrepot.objects.get_or_create(
                entrepot=entrepot, produit_id=produit_id,
                defaults={'quantite': quantite}
            )
            if not _:
                stock.quantite = quantite
                stock.save()
            return JsonResponse({'success': True, 'quantite': float(quantite)})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST requis'})


@login_required
def brasserie_supprimer(request, produit_id):
    """Supprimer un produit brasserie (soft delete)"""
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_GROUPS for g in user_groups):
        messages.error(request, "Acces refuse.")
        return redirect('admin:index')

    produit = get_object_or_404(Produit, id=produit_id)
    if request.method == 'POST':
        produit.actif = False
        produit.save()
        messages.success(request, f'Produit {produit.nom} supprime')
        return redirect('dashboard:brasserie_produits')

    context = {'produit': produit}
    return render(request, 'dashboard/brasserie_supprimer.html', context)

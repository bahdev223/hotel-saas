from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.db import transaction
import json

from ..models import PointVente, CaissePointVente
from ..services.pos_service import PointVenteService
from apps.tresorerie.models import Caisse
from apps.stock.models import Produit
from apps.restaurant.models import MenuModel
from apps.clients.models import Client
from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF


@login_required
def api_produits(request):
    from apps.hotel.models import UniteModel

    pv_slug = request.GET.get('point_vente_slug')
    entrepot_id_param = request.GET.get('entrepot_id')
    stocks_dict = {}
    if pv_slug:
        pv = get_object_or_404(PointVente, code__iexact=pv_slug, actif=True)
        entrepot_ids = PointVenteService.get_entrepot_ids(pv)
        stocks_dict = PointVenteService.get_stocks_dict(entrepot_ids, entrepot_id_param)

    produits = Produit.objects.filter(actif=True, est_vendable=True).select_related('categorie', 'domaine')
    menus = MenuModel.objects.filter(actif=True, visible_dans_pos=True).order_by('ordre_affichage', 'nom').distinct()
    unites = UniteModel.objects.filter(actif=True).order_by('type_unite', 'code').distinct()

    categories = PointVenteService.build_categories_dict(produits, menus, unites, stocks_dict)
    sous_categories = PointVenteService.build_sous_categories(categories)

    return JsonResponse({'success': True, 'categories': categories, 'sous_categories': sous_categories})


@login_required
@csrf_exempt
def api_ajouter_caisse(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            caisse = Caisse.objects.create(
                code=data.get('code'), nom=data.get('nom'),
                type_caisse=data.get('type_caisse', 'PRINCIPALE'),
                solde=data.get('solde_initial', 0), actif=True, responsable=request.user,
            )
            return JsonResponse({'success': True, 'caisse_id': caisse.id})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
    return JsonResponse({'success': False, 'error': 'POST required'})


@csrf_exempt
@login_required
def api_ajouter_point_vente(request):
    if not request.user.is_superuser and not request.user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        return JsonResponse({'success': False, 'error': 'Action non autoris\u00e9e'}, status=403)
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})
    try:
        from django.db import transaction as db_transaction
        data = json.loads(request.body)
        nom = data.get('nom', '').strip()
        caisse_id = data.get('caisse_id')

        if not nom or not caisse_id:
            return JsonResponse({'success': False, 'error': 'Le nom et le compte sont obligatoires'})

        from django.shortcuts import get_object_or_404
        from ..models import PointVente
        from apps.tresorerie.models import Caisse

        caisse = get_object_or_404(Caisse, id=caisse_id, actif=True)

        prefixe = 'PV'
        dernier = PointVente.objects.filter(code__startswith=prefixe).order_by('code').last()
        if dernier:
            try:
                num = int(dernier.code.replace(prefixe + '-', '')) + 1
            except ValueError:
                num = PointVente.objects.count() + 1
        else:
            num = 1
        code = f"{prefixe}-{num:03d}"

        with db_transaction.atomic():
            point = PointVente.objects.create(
                code=code, nom=nom, type='AUTRE', actif=True,
            )
            CaissePointVente.objects.create(point_vente=point, caisse=caisse, principale=True)

        return JsonResponse({
            'success': True,
            'point': {
                'id': point.id, 'code': point.code, 'nom': point.nom,
                'caisse_nom': caisse.nom,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_liste_ventes(request):
    from ..models import Vente
    from ..models.commande import Commande
    from django.db.models import Q

    pv = request.GET.get('point_vente')
    dd = request.GET.get('date_debut')
    df = request.GET.get('date_fin')
    employe_id = request.GET.get('employe_id')
    heure_debut = request.GET.get('heure_debut')
    heure_fin = request.GET.get('heure_fin')
    domaine = request.GET.get('domaine')
    session_id = request.GET.get('session_id')
    produit_id = request.GET.get('produit_id')

    DOMAINE_MAP = {
        'brasserie': ['BAR', 'AUTRE'],
        'restaurant': ['RESTAURATION', 'ROOM_SERVICE'],
        'hotel': ['RECEPTION'],
    }

    ventes_qs = Vente.objects.all().order_by('-created_at')
    if pv:
        ventes_qs = ventes_qs.filter(point_vente_id=pv)
    if domaine and domaine in DOMAINE_MAP:
        ventes_qs = ventes_qs.filter(point_vente__type__in=DOMAINE_MAP[domaine])
    if dd:
        ventes_qs = ventes_qs.filter(created_at__date__gte=dd)
    if df:
        ventes_qs = ventes_qs.filter(created_at__date__lte=df)
    if heure_debut:
        ventes_qs = ventes_qs.filter(created_at__time__gte=heure_debut)
    if heure_fin:
        ventes_qs = ventes_qs.filter(created_at__time__lte=heure_fin)
    if employe_id:
        ventes_qs = ventes_qs.filter(Q(caissier_id=employe_id) | Q(encaisse_par_id=employe_id))
    if session_id:
        ventes_qs = ventes_qs.filter(session_caisse_id=session_id)
    if produit_id:
        ventes_qs = ventes_qs.filter(lignes__produit_id=produit_id).distinct()

    cmd_qs = Commande.objects.filter(
        Q(statut='SERVIE') | Q(statut='LIVREE'), vente__isnull=True
    ).select_related('point_vente', 'created_by').order_by('-date_commande')
    if pv:
        cmd_qs = cmd_qs.filter(point_vente_id=pv)
    if dd:
        cmd_qs = cmd_qs.filter(date_commande__date__gte=dd)
    if df:
        cmd_qs = cmd_qs.filter(date_commande__date__lte=df)
    if employe_id:
        cmd_qs = cmd_qs.filter(created_by_id=employe_id)
    if domaine and domaine in DOMAINE_MAP:
        cmd_qs = cmd_qs.filter(point_vente__type__in=DOMAINE_MAP[domaine])
    if session_id:
        cmd_qs = cmd_qs.none()
    if produit_id:
        cmd_qs = cmd_qs.filter(lignes__produit_id=produit_id).distinct()

    data = []

    for v in ventes_qs[:200]:
        lignes = []
        for l in v.lignes.select_related('produit', 'menu').all()[:5]:
            lignes.append({
                'nom': l.article_nom, 'quantite': float(l.quantite),
                'prix': float(l.prix_unitaire), 'total': float(l.total_ligne),
            })
        domain = ''
        if v.point_vente:
            domain = next((d for d, emps in DOMAINE_MAP.items() if v.point_vente.type in emps), '')
        data.append({
            'id': v.id, 'numero': v.numero, 'type': 'vente',
            'date': v.created_at.strftime('%d/%m/%Y %H:%M'),
            'dateOrig': v.created_at.isoformat(),
            'point_vente': v.point_vente.nom if v.point_vente else '',
            'point_vente_id': v.point_vente_id,
            'client': v.client.nom_complet if v.client else (v.client_nom or ''),
            'montant': float(v.montant_total),
            'mode_paiement': v.get_mode_paiement_display() if v.mode_paiement else '',
            'mode_paiement_code': v.mode_paiement or '',
            'statut': v.get_statut_display() if v.statut else 'Pay\u00e9e',
            'statut_code': 'PAYEE' if v.statut == 'PAYEE' else v.statut,
            'caissier': v.caissier.nom_complet if v.caissier else (v.encaisse_par.nom_complet if v.encaisse_par else ''),
            'caissier_id': v.caissier_id or v.encaisse_par_id,
            'session_id': v.session_caisse_id, 'lignes': lignes,
            'lignes_count': v.lignes.count(), 'domaine': domain,
        })

    for c in cmd_qs:
        lignes = []
        for ligne in c.lignes.all().select_related('unite', 'produit', 'menu')[:5]:
            nom = (ligne.unite.nom if ligne.unite else
                   ligne.produit.nom if ligne.produit else
                   ligne.menu.nom if ligne.menu else 'Article')
            lignes.append({
                'nom': nom, 'quantite': float(ligne.quantite or 1),
                'prix': float(ligne.prix_unitaire), 'total': float(ligne.total_ligne),
            })
        data.append({
            'id': c.id, 'numero': c.numero, 'type': 'vente',
            'date': c.date_commande.strftime('%d/%m/%Y %H:%M'),
            'dateOrig': c.date_commande.isoformat(),
            'point_vente': c.point_vente.nom if c.point_vente else '',
            'point_vente_id': c.point_vente_id, 'client': c.client_nom or 'Anonyme',
            'montant': float(c.montant_total), 'mode_paiement': '-',
            'mode_paiement_code': '', 'statut': c.get_statut_display(),
            'statut_code': c.statut,
            'caissier': c.created_by.nom_complet if c.created_by else '',
            'caissier_id': c.created_by_id, 'lignes': lignes,
            'lignes_count': c.lignes.count(), 'is_commande': True,
        })

    return JsonResponse({'success': True, 'ventes': data})


@login_required
@require_GET
def api_recherche_clients(request):
    from django.db.models import Q
    search = request.GET.get('search', '').strip()
    qs = Client.objects.filter(statut='ACTIF')
    if search:
        qs = qs.filter(Q(nom__icontains=search) | Q(prenom__icontains=search) | Q(telephone__icontains=search))
    qs = qs[:20]
    return JsonResponse({
        'success': True,
        'clients': [{'id': c.id, 'nom': c.nom_complet, 'telephone': c.telephone, 'adresse': c.adresse or ''} for c in qs]
    })


@login_required
@csrf_exempt
@require_http_methods(["POST"])
def api_creer_client(request):
    try:
        data = json.loads(request.body)
        nom = data.get('nom', '').strip()
        telephone = data.get('telephone', '').strip()
        adresse = data.get('adresse', '').strip()

        if not nom:
            return JsonResponse({'success': False, 'error': 'Le nom est obligatoire'})
        if not telephone:
            return JsonResponse({'success': False, 'error': 'Le t\u00e9l\u00e9phone est obligatoire'})

        existing = Client.objects.filter(telephone=telephone).first()
        if existing:
            return JsonResponse({
                'success': True,
                'client': {'id': existing.id, 'nom': existing.nom_complet, 'telephone': existing.telephone, 'adresse': existing.adresse or ''},
                'existant': True,
            })

        client = Client.objects.create(nom=nom, telephone=telephone, adresse=adresse, statut='ACTIF')

        return JsonResponse({
            'success': True,
            'client': {'id': client.id, 'nom': client.nom_complet, 'telephone': client.telephone, 'adresse': client.adresse or ''},
            'existant': False,
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

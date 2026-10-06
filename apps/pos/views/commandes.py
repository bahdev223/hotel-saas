# apps/pos/views/commandes.py
# apps/pos/views/commandes.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db import models, transaction
from decimal import Decimal
import json
import uuid

from ..models import Commande, LigneCommande, PointVente, Livraison, Livreur, PointVenteEntrepot
from ..services.pos_service import PointVenteService
from apps.restaurant.models import TableModel
from apps.stock.models import Produit, StockEntrepot, Entrepot
from apps.stock.services.mouvement_service import MouvementStockService
from apps.restaurant.models import MenuModel
from apps.restaurant.services.restaurant_service import (
    RestaurantService,
    RestaurantWorkflowError,
)
from apps.rh.models import Employe
from .pos import a_vue_globale_commandes, get_pv_courant_id
from ..services.access_service import POSAccessService
from ..constants import ActionPOS, POINTS_VENTE_OPERATIONNELS


def deduire_stock_commande(commande, entrepot_id=None):
    """Déduire le stock de l'entrepôt lié au point de vente.
    Délègue au service centralisé RestaurantConsumptionService.
    Idempotent : une commande déjà déduite ne l'est jamais deux fois."""
    from apps.restaurant.services.consumption_service import RestaurantConsumptionService
    entrepot = commande.entrepot
    if not entrepot and entrepot_id:
        from apps.stock.models import Entrepot
        try:
            entrepot = Entrepot.objects.get(id=entrepot_id)
        except Exception:
            pass
    if not entrepot:
        entrepot = commande.point_vente.entrepot
    return RestaurantConsumptionService.consommer_commande(
        commande=commande, entrepot=entrepot,
        utilisateur=str(commande.created_by) if commande.created_by else 'POS',
    )


def _generer_facture_commande(commande):
    """Generer une facture pour une commande servie/livree"""
    try:
        from apps.facturation.services import FactureGenerators
        facture = FactureGenerators.depuis_commande(commande)
        facture.emettre()
    except Exception as e:
        print(f"Erreur generation facture: {e}")


def _deduire_emballage(commande):
    """Déduire 1 emballage du stock pour une commande à emporter"""
    try:
        pv = commande.point_vente
        entrepot = pv.entrepot
        if not entrepot:
            ep = PointVenteEntrepot.objects.filter(point_vente=pv).first()
            if ep:
                entrepot = ep.entrepot
            else:
                return
        emballage = Produit.objects.filter(
            actif=True,
            domaine__nom='RESTAURANT'
        ).filter(
            models.Q(code__istartswith='EMB') | models.Q(categorie__nom__iexact='EMBALLAGE')
        ).first()
        if not emballage:
            return
        MouvementStockService.sortie_stock(
            produit=emballage,
            entrepot=entrepot,
            quantite=1,
            utilisateur=str(commande.created_by.user.username) if commande.created_by and commande.created_by.user else 'POS',
            motif='consommation',
            reference=commande.numero,
            raison=f"Emballage commande {commande.numero}"
        )
    except Exception as e:
        print(f"Erreur dÃ©duction emballage: {e}")


@login_required
def dashboard_commandes(request):
    """Dashboard principal des commandes"""
    point_vente_id = request.GET.get('point_vente')

    if a_vue_globale_commandes(request.user):
        # Patron / Manager / RAF : vue globale (avec sélecteur de PV optionnel)
        if point_vente_id:
            point_vente_selected = get_object_or_404(
                PointVente,
                id=point_vente_id,
                type__in=POINTS_VENTE_OPERATIONNELS,
            )
            commandes = Commande.objects.filter(point_vente=point_vente_selected)
        else:
            commandes = Commande.objects.filter(
                point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
            )
            point_vente_selected = None
    else:
        # Employé simple : uniquement SES commandes, dans SON PV courant
        employe = getattr(request.user, 'employe', None)
        pv_courant_id = get_pv_courant_id(request)
        commandes = Commande.objects.filter(created_by=employe, point_vente_id=pv_courant_id)
        point_vente_selected = PointVente.objects.filter(id=pv_courant_id).first()

    commandes = commandes.order_by('-created_at')

    # Commandes par statut
    commandes_attente = commandes.filter(statut='EN_ATTENTE')
    commandes_preparation = commandes.filter(statut='EN_PREPARATION')
    commandes_prete = commandes.filter(statut='PRETE')
    commandes_terminees = commandes.filter(statut__in=['SERVIE', 'LIVREE', 'ANNULEE'])[:50]
    
    points_vente = PointVente.objects.filter(
        actif=True,
        type__in=POINTS_VENTE_OPERATIONNELS,
    )
    
    context = {
        'points_vente': points_vente,
        'point_vente_selected': point_vente_selected,
        'commandes_attente': commandes_attente,
        'commandes_preparation': commandes_preparation,
        'commandes_prete': commandes_prete,
        'commandes_terminees': commandes_terminees,
    }
    return render(request, 'pos/commandes/dashboard.html', context)


@login_required
def cuisine_dashboard(request):
    """Interface cuisine : commandes Restaurant uniquement."""
    commandes = Commande.objects.filter(
        statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRETE'],
        point_vente__type='RESTAURATION',
    ).order_by('-created_at')
    if not a_vue_globale_commandes(request.user):
        pv_ids = list(
            POSAccessService.points_accessibles(
                user=request.user,
                action=ActionPOS.ACCEDER,
            )
            .filter(type='RESTAURATION')
            .values_list('id', flat=True)
        )
        commandes = commandes.filter(point_vente_id__in=pv_ids)
    
    context = {
        'commandes_attente': commandes.filter(statut='EN_ATTENTE'),
        'commandes_preparation': commandes.filter(statut='EN_PREPARATION'),
        'commandes_prete': commandes.filter(statut='PRETE'),
    }
    return render(request, 'pos/commandes/cuisine.html', context)


@login_required
def detail_commande(request, commande_id):
    """Détail d'une commande (API)"""
    commande = get_object_or_404(
        Commande.objects.select_related("point_vente"),
        id=commande_id,
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )
    if not a_vue_globale_commandes(request.user):
        decision = POSAccessService.check(
            user=request.user,
            point_vente=commande.point_vente,
            action=ActionPOS.ACCEDER,
        )
        if not decision.allowed:
            return JsonResponse({
                'success': False,
                'error_code': decision.reason,
                'error': f"Accès refusé ({decision.reason}).",
            }, status=403)
    lignes = commande.lignes.all()
    
    data = {
        'id': commande.id,
        'numero': commande.numero,
        'type_commande': commande.get_type_commande_display(),
        'statut': commande.get_statut_display(),
        'statut_code': commande.statut,
        'client_id': commande.client.id if commande.client else None,
        'client_nom': commande.client.nom_complet if commande.client else (commande.client_nom or 'Anonyme'),
        'client_telephone': commande.client_telephone,
        'adresse_livraison': commande.adresse_livraison,
        'table_numero': commande.table.numero if commande.table else None,
        'montant_total': float(commande.montant_total),
        'facture_numero': commande.facture.numero if hasattr(commande, 'facture') and commande.facture else None,
        'facture_id': commande.facture.id if hasattr(commande, 'facture') and commande.facture else None,
        'notes': commande.notes,
        'date_commande': commande.date_commande.strftime('%d/%m/%Y %H:%M'),
        'temps_attente': commande.temps_attente_minutes,
        'lignes': [
            {
                'article': l.article_nom,
                'article_id': l.produit_id or l.menu_id or l.unite_id,
                'quantite': float(l.quantite) if not l.unite_id else float(l.heures),
                'prix_unitaire': float(l.prix_unitaire),
                'total': float(l.total_ligne),
                'type': l.type_article,
                'notes': l.notes
            }
            for l in lignes
        ]
    }
    return JsonResponse({'success': True, 'commande': data})


@login_required
def liste_commandes_api(request):
    """API pour récupérer la liste des commandes filtrée"""
    point_vente_id = request.GET.get('point_vente')
    statut = request.GET.get('statut')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    
    commandes = Commande.objects.filter(
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    ).select_related('point_vente', 'facture')

    # Exclure les commandes déjà payées (liées à une vente) ou annulées
    commandes = commandes.filter(vente__isnull=True).exclude(statut='ANNULEE')

    if a_vue_globale_commandes(request.user):
        # Patron / Manager / RAF : vue globale, filtre PV optionnel
        if point_vente_id:
            commandes = commandes.filter(point_vente_id=point_vente_id)
    else:
        # Employé simple : uniquement SES commandes, dans SON PV courant
        employe = getattr(request.user, 'employe', None)
        commandes = commandes.filter(created_by=employe)
        pv_courant_id = get_pv_courant_id(request)
        if pv_courant_id:
            commandes = commandes.filter(point_vente_id=pv_courant_id)
    if statut:
        statuts = statut.split(',')
        commandes = commandes.filter(statut__in=statuts)
    if date_debut:
        commandes = commandes.filter(date_commande__date__gte=date_debut)
    if date_fin:
        commandes = commandes.filter(date_commande__date__lte=date_fin)
    
    data = []
    for c in commandes[:100]:
        lignes_data = []
        for ligne in c.lignes.all().select_related('unite', 'produit', 'menu'):
            if ligne.unite:
                lignes_data.append({
                    'type': 'LOCATION',
                    'nom': ligne.unite.nom,
                    'heures': ligne.heures,
                    'prix': float(ligne.prix_unitaire),
                })
            elif ligne.produit:
                lignes_data.append({
                    'type': 'PRODUIT',
                    'nom': ligne.produit.nom,
                    'quantite': float(ligne.quantite),
                    'prix': float(ligne.prix_unitaire),
                })
            elif ligne.menu:
                lignes_data.append({
                    'type': 'MENU',
                    'nom': ligne.menu.nom,
                    'quantite': float(ligne.quantite),
                    'prix': float(ligne.prix_unitaire),
                })
        livraison = getattr(c, 'livraison', None)
        data.append({
            'id': c.id,
            'numero': c.numero,
            'point_vente': c.point_vente.nom,
            'type': c.get_type_commande_display(),
            'type_code': c.type_commande,
            'statut': c.get_statut_display(),
            'statut_code': c.statut,
            'client': c.client_nom or 'Anonyme',
            'montant': float(c.montant_total),
            'frais_livraison': float(c.frais_livraison),
            'adresse_livraison': c.adresse_livraison,
            'temps_attente': c.temps_attente_minutes,
            'date': c.date_commande.strftime('%H:%M'),
            'lignes_count': c.lignes.count(),
            'lignes': lignes_data,
            'facture_id': c.facture.id if hasattr(c, 'facture') and c.facture else None,
            'facture_numero': c.facture.numero if hasattr(c, 'facture') and c.facture else None,
            'livraison': {
                'id': livraison.id,
                'statut': livraison.get_statut_display(),
                'statut_code': livraison.statut,
                'adresse': livraison.adresse,
                'frais': float(livraison.frais),
                'nom_livreur': livraison.nom_livreur,
            } if livraison else None,
        })
    
    return JsonResponse({'success': True, 'commandes': data})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def changer_statut_commande(request, commande_id):
    """Transition contrôlée d'une commande Bar / Restaurant."""
    try:
        data = json.loads(request.body or "{}")
        commande = get_object_or_404(
            Commande.objects.select_related("point_vente", "table"),
            id=commande_id,
            point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
        )
        nouveau_statut = data.get("statut")
        statuts_valides = {value for value, _ in Commande.STATUT_CHOICES}
        if nouveau_statut not in statuts_valides:
            return JsonResponse({
                "success": False,
                "error_code": "STATUT_COMMANDE_INVALIDE",
                "error": "Statut de commande invalide.",
            }, status=400)

        # Restaurant sur place : le workflow métier est strictement séquencé.
        if commande.point_vente.type == "RESTAURATION":
            if nouveau_statut == "EN_PREPARATION":
                commande = RestaurantService.demarrer_preparation(
                    commande=commande,
                    user=request.user,
                )
            elif nouveau_statut == "PRETE":
                commande = RestaurantService.marquer_prete(
                    commande=commande,
                    user=request.user,
                )
            elif nouveau_statut == "SERVIE":
                commande = RestaurantService.servir(
                    commande=commande,
                    user=request.user,
                )
            elif nouveau_statut == "ANNULEE":
                decision = POSAccessService.check(
                    user=request.user,
                    point_vente=commande.point_vente,
                    action=ActionPOS.ANNULER_VENTE,
                )
                if not decision.allowed:
                    return JsonResponse({
                        "success": False,
                        "error_code": decision.reason,
                        "error": f"Annulation refusée ({decision.reason}).",
                    }, status=403)
                commande.annuler()
                RestaurantService.liberer_table_si_terminee(commande)
            elif (
                commande.type_commande == "LIVRAISON"
                and nouveau_statut in ("EN_COURS_DE_LIVRAISON", "LIVREE")
            ):
                decision = POSAccessService.check(
                    user=request.user,
                    point_vente=commande.point_vente,
                    action=ActionPOS.SERVIR_COMMANDE,
                )
                if not decision.allowed:
                    return JsonResponse({
                        "success": False,
                        "error_code": decision.reason,
                        "error": f"Service refusé ({decision.reason}).",
                    }, status=403)
                if nouveau_statut == "EN_COURS_DE_LIVRAISON":
                    if commande.statut != "PRETE":
                        raise RestaurantWorkflowError(
                            "Une livraison doit être prête avant son départ."
                        )
                    commande.demarrer_livraison()
                else:
                    if commande.statut != "EN_COURS_DE_LIVRAISON":
                        raise RestaurantWorkflowError(
                            "La commande doit être en cours de livraison."
                        )
                    commande.livrer()
            else:
                raise RestaurantWorkflowError(
                    "Transition Restaurant interdite. Utilisez Cuisine → Prête → Service."
                )

        # Bar : workflow court, sans KDS Restaurant obligatoire.
        else:
            action_requise = (
                ActionPOS.ANNULER_VENTE
                if nouveau_statut == "ANNULEE"
                else ActionPOS.VENDRE
            )
            decision = POSAccessService.check(
                user=request.user,
                point_vente=commande.point_vente,
                action=action_requise,
            )
            if not decision.allowed:
                return JsonResponse({
                    "success": False,
                    "error_code": decision.reason,
                    "error": f"Accès refusé ({decision.reason}).",
                }, status=403)

            if nouveau_statut == "ANNULEE":
                commande.annuler()
            elif nouveau_statut == "SERVIE":
                if commande.statut not in ("EN_ATTENTE", "PRETE"):
                    raise ValueError("Commande Bar non servable dans cet état.")
                commande.servir()
            else:
                commande.statut = nouveau_statut
                commande.save(update_fields=["statut", "updated_at"])

        return JsonResponse({
            "success": True,
            "statut": commande.statut,
            "statut_display": commande.get_statut_display(),
            "message": f"Commande #{commande.numero} : {commande.get_statut_display()}",
        })

    except RestaurantWorkflowError as exc:
        return JsonResponse(
            {"success": False, "error": str(exc)},
            status=409,
        )
    except Exception as exc:
        return JsonResponse(
            {"success": False, "error": str(exc)},
            status=400,
        )


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_payer_commande(request, commande_id):
    """Payer une commande — délègue à CommandeSettlementService"""
    try:
        commande = get_object_or_404(
            Commande.objects.select_related("point_vente"),
            id=commande_id,
            point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
        )
        data = json.loads(request.body)
        mode_paiement = data.get('mode_paiement', 'ESPECES')

        # Le service de règlement vérifie la session financière, son
        # propriétaire et l'éventuelle fenêtre de passation.

        from apps.paiements.services.commande_settlement_service import (
            CommandeSettlementService,
            CommandeSettlementError,
        )

        result = CommandeSettlementService.regler(
            commande=commande,
            montant=commande.montant_total,
            mode_paiement=mode_paiement,
            utilisateur=request.user,
            notes=data.get('notes', ''),
        )

        return JsonResponse({
            'success': True,
            'vente_id': result['vente'].id,
            'numero': result['vente'].numero,
            'montant_total': float(result['montant']),
            'mode': result['mode'],
            'message': 'Paiement effectué',
        })

    except CommandeSettlementError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    


# apps/pos/views/commandes.py - AJOUTER CETTE FONCTION

@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_creer_commande(request):
    """Créer une commande"""
    try:
        from apps.clients.models import Client
        data = json.loads(request.body)
        
        point_vente = get_object_or_404(
            PointVente,
            code__iexact=data.get('point_vente_slug'),
            actif=True,
            type__in=POINTS_VENTE_OPERATIONNELS,
        )
        employe = Employe.objects.filter(user=request.user, actif=True).first()
        if employe is None:
            return JsonResponse({
                'success': False,
                'error_code': 'AUCUN_PROFIL_EMPLOYE',
                'error': "Un profil employé actif est obligatoire pour créer une commande POS.",
            }, status=403)

        decision = POSAccessService.check(
            user=request.user,
            employe=employe,
            point_vente=point_vente,
            action=ActionPOS.VENDRE,
        )
        if not decision.allowed:
            return JsonResponse({
                'success': False,
                'error_code': decision.reason,
                'error': f"Création de commande refusée ({decision.reason}).",
            }, status=403)

        # Prévalidation complète AVANT toute écriture SQL.
        from django.db.models import Sum
        from apps.restaurant.services.menu_service import MenuService

        entrepot_utilise = PointVenteService.get_entrepot_utilise(
            point_vente, data.get('entrepot_id')
        )
        lignes_payload = data.get('lignes', [])
        if not isinstance(lignes_payload, list) or not lignes_payload:
            return JsonResponse({
                'success': False,
                'error_code': 'LIGNES_REQUISES',
                'error': "La commande doit contenir au moins un article.",
            }, status=400)

        for index, item in enumerate(lignes_payload, start=1):
            type_art = item.get('type_article', 'PRODUIT')
            if type_art not in ('PRODUIT', 'MENU', 'LOCATION'):
                return JsonResponse({
                    'success': False,
                    'error_code': 'TYPE_ARTICLE_INVALIDE',
                    'error': f"Ligne #{index}: type d'article inconnu ({type_art}).",
                }, status=400)

            try:
                qte = Decimal(str(item.get('quantite', 1)))
            except Exception:
                return JsonResponse({
                    'success': False,
                    'error_code': 'QUANTITE_INVALIDE',
                    'error': f"Ligne #{index}: quantité invalide.",
                }, status=400)
            if qte <= 0:
                return JsonResponse({
                    'success': False,
                    'error_code': 'QUANTITE_INVALIDE',
                    'error': f"Ligne #{index}: la quantité doit être strictement positive.",
                }, status=400)

            if type_art == 'LOCATION':
                return JsonResponse({
                    'success': False,
                    'error_code': 'HORS_PERIMETRE_POS',
                    'error': (
                        "Le POS Bar/Restaurant ne gère pas les chambres ou locations. "
                        "Utilisez le domaine Hébergement."
                    ),
                }, status=400)

            if type_art == 'PRODUIT':
                produit_id = item.get('produit_id')
                produit = Produit.objects.filter(
                    id=produit_id,
                    actif=True,
                ).first()
                if produit is None:
                    return JsonResponse({
                        'success': False,
                        'error_code': 'PRODUIT_INVALIDE',
                        'error': f"Ligne #{index}: produit introuvable ou inactif.",
                    }, status=400)

                stock_total = Decimal('0')
                if entrepot_utilise:
                    stock_total = (
                        StockEntrepot.objects.filter(
                            entrepot_id=entrepot_utilise,
                            produit_id=produit_id,
                        ).aggregate(total=Sum('quantite'))['total']
                        or Decimal('0')
                    )
                if stock_total < qte:
                    return JsonResponse({
                        'success': False,
                        'error_code': 'STOCK_INSUFFISANT',
                        'error': (
                            f"Stock insuffisant pour {produit.nom} : "
                            f"{float(stock_total)} disponible(s), "
                            f"{float(qte)} demandé(s)."
                        ),
                    }, status=400)

            elif type_art == 'MENU':
                menu = MenuModel.objects.filter(
                    id=item.get('menu_id'),
                    actif=True,
                ).first()
                if menu is None:
                    return JsonResponse({
                        'success': False,
                        'error_code': 'MENU_INVALIDE',
                        'error': f"Ligne #{index}: menu introuvable ou inactif.",
                    }, status=400)

                validation = MenuService.valider_choix_menu(
                    menu,
                    item.get('choix', []),
                )
                if not validation['valid']:
                    return JsonResponse({
                        'success': False,
                        'error_code': 'CHOIX_INVALIDE',
                        'error': '; '.join(validation['errors']),
                    }, status=400)

        type_commande = data.get('type_commande', 'SUR_PLACE')
        if type_commande not in dict(Commande.TYPE_CHOICES):
            return JsonResponse({
                'success': False,
                'error_code': 'TYPE_COMMANDE_INVALIDE',
                'error': "Type de commande invalide.",
            }, status=400)

        restaurant_table = None
        nombre_couverts = data.get('nombre_couverts')
        if point_vente.type == 'RESTAURATION' and type_commande == 'SUR_PLACE':
            table_id = data.get('table_id')
            if not table_id:
                return JsonResponse({
                    'success': False,
                    'error_code': 'TABLE_REQUISE',
                    'error': "Une commande sur place Restaurant doit être liée à une table.",
                }, status=400)
            restaurant_table = (
                TableModel.objects
                .select_for_update()
                .filter(
                    id=table_id,
                    actif=True,
                    salle__point_vente=point_vente,
                )
                .select_related('salle')
                .first()
            )
            if restaurant_table is None:
                return JsonResponse({
                    'success': False,
                    'error_code': 'TABLE_INVALIDE',
                    'error': "Cette table n'appartient pas à ce Restaurant.",
                }, status=400)
            if RestaurantService.commande_active_table(restaurant_table):
                return JsonResponse({
                    'success': False,
                    'error_code': 'TABLE_OCCUPEE',
                    'error': f"Table {restaurant_table.numero} possède déjà une commande active.",
                }, status=409)

        client_id = data.get('client_id')
        client_obj = None
        if client_id:
            try:
                client_obj = Client.objects.get(id=client_id)
            except Client.DoesNotExist:
                pass
        
        commande = Commande.objects.create(
            point_vente=point_vente,
            entrepot_id=entrepot_utilise,
            type_commande=type_commande,
            client=client_obj,
            client_nom=data.get('client_nom', ''),
            client_telephone=data.get('client_telephone', ''),
            adresse_livraison=data.get('adresse_livraison', ''),
            frais_livraison=Decimal(str(data.get('frais_livraison', 0))),
            notes=data.get('notes', ''),
            created_by=employe,
            statut='EN_ATTENTE'
        )
        
        total = Decimal('0')
        
        for item in lignes_payload:
            type_art = item.get('type_article', 'PRODUIT')
            qte = Decimal(str(item.get('quantite', 1)))

            if type_art == 'LOCATION':
                # Impossible après prévalidation ; garde-fou transactionnel.
                raise ValueError("Une ligne Hébergement a atteint le moteur POS.")
            elif type_art == 'MENU':
                menu = get_object_or_404(MenuModel, id=item.get('menu_id'), actif=True)
                # Les choix ont déjà été validés avant toute écriture.
                choix_list = item.get('choix', [])
                prix = Decimal(str(menu.prix_vente))
                ligne = LigneCommande.objects.create(commande=commande, menu=menu, quantite=qte, prix_unitaire=prix)
                # Créer les choix client pour ce menu
                from apps.restaurant.models import ChoixLigneCommande
                for choix_data in choix_list:
                    choix_recette_id = choix_data.get('recette_id')
                    if not choix_recette_id:
                        continue
                    from apps.restaurant.models import RecetteModel
                    choix_recette = RecetteModel.objects.filter(id=choix_recette_id).first()
                    if not choix_recette:
                        continue
                    choix_cout = choix_recette.cout_unitaire_rendement()
                    ChoixLigneCommande.objects.create(
                        ligne_commande=ligne,
                        groupe=choix_data.get('groupe', 'PLAT'),
                        recette=choix_recette,
                        ligne_menu_id=choix_data.get('ligne_menu_id'),
                        quantite=choix_data.get('quantite', 1),
                        prix_supplement=choix_data.get('prix_supplement', 0),
                        nom_recette_snapshot=choix_recette.nom,
                        cout_unitaire_snapshot=choix_cout,
                    )
                    # Ajouter le prix du supplément au total
                    prix_supp = Decimal(str(choix_data.get('prix_supplement', 0)))
                    if prix_supp > 0:
                        prix += prix_supp
                        ligne.prix_unitaire = prix
                        ligne.save(update_fields=['prix_unitaire'])
                total += qte * prix
            else:
                produit = get_object_or_404(Produit, id=item.get('produit_id'), actif=True)
                prix = Decimal(str(produit.prix_vente))
                LigneCommande.objects.create(commande=commande, produit=produit, quantite=qte, prix_unitaire=prix)
                total += qte * prix
        
        commande.montant_total = total + commande.frais_livraison
        commande.save(update_fields=['montant_total', 'updated_at'])

        if restaurant_table is not None:
            RestaurantService.lier_commande_table(
                commande=commande,
                table=restaurant_table,
                employe=employe,
                user=request.user,
                nombre_couverts=nombre_couverts,
            )

        # Créer une livraison si le type est LIVRAISON
        if commande.type_commande == 'LIVRAISON' and commande.adresse_livraison:
            Livraison.objects.create(
                commande=commande,
                adresse=commande.adresse_livraison,
                frais=commande.frais_livraison,
                statut='EN_ATTENTE'
            )
        
        # Déduire l'emballage si la commande est EMPORTER
        if commande.type_commande == 'EMPORTER' and (
            commande.point_vente.entrepot or
            PointVenteEntrepot.objects.filter(point_vente=commande.point_vente).exists()
        ):
            _deduire_emballage(commande)
        
        return JsonResponse({
            'success': True,
            'commande_id': commande.id,
            'numero': commande.numero,
            'montant_total': float(commande.montant_total),
            'frais_livraison': float(commande.frais_livraison),
            'table_id': commande.table_id,
            'table_numero': commande.table.numero if commande.table else None,
            'message': 'Commande créée avec succès'
        })
        
    except Exception as e:
        # La vue est sous @transaction.atomic : toute erreur survenue après le
        # début des écritures doit invalider explicitement la transaction.
        transaction.set_rollback(True)
        return JsonResponse(
            {'success': False, 'error': str(e)},
            status=400,
        )


@login_required
def api_vente_recu(request, vente_id):
    """API : retourne les données d'une vente pour réimpression du ticket"""
    from ..models import Vente
    v = get_object_or_404(
        Vente.objects.select_related("point_vente"),
        id=vente_id,
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    )
    if not a_vue_globale_commandes(request.user):
        decision = POSAccessService.check(
            user=request.user,
            point_vente=v.point_vente,
            action=ActionPOS.ACCEDER,
        )
        if not decision.allowed:
            return JsonResponse({
                'success': False,
                'error_code': decision.reason,
                'error': f"Accès au ticket refusé ({decision.reason}).",
            }, status=403)
    lignes = []
    for l in v.lignes.select_related('produit', 'menu').all():
        lignes.append({
            'description': l.produit.nom if l.produit else (l.menu.nom if l.menu else 'Article'),
            'quantite': float(l.quantite),
            'prix_unitaire': float(l.prix_unitaire),
            'total_ttc': float(l.total_ligne),
        })

    return JsonResponse({
        'success': True,
        'recu': {
            'reference': v.numero,
            'montant': float(v.montant_total),
            'mode_label': v.get_mode_paiement_display(),
            'date': v.created_at.isoformat(),
            'caisse': v.caisse.nom if v.caisse else '',
            'servi_par': v.caissier.nom_complet if v.caissier else '',
            'point_vente': v.point_vente.nom if v.point_vente else '',
            'client_nom': v.client_nom or '',
            'source_numero': v.numero,
            'lignes': lignes,
        }
    })


@csrf_exempt
@login_required
@require_http_methods(["GET"])
def api_raf_liste_commandes_payees(request):
    """API RAF : liste les commandes PAYÉES annulables."""
    from apps.pos.models import Commande

    if not request.user.groups.filter(name='RAF').exists():
        return JsonResponse({'success': False, 'error': 'Accès refusé'})

    commandes = Commande.objects.filter(
        statut='PAYEE',
        vente__isnull=False,
        point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
    ).select_related('point_vente', 'vente', 'client').order_by('-date_commande')[:50]

    result = []
    for c in commandes:
        vente = c.vente
        result.append({
            'id': c.id,
            'numero': c.numero,
            'point_vente': c.point_vente.nom if c.point_vente else 'N/A',
            'client': c.client.nom_complet if c.client else (c.client_nom or 'Anonyme'),
            'montant': float(c.montant_total),
            'mode_paiement': vente.mode_paiement if vente else 'N/A',
            'date': c.date_commande.strftime('%d/%m/%Y %H:%M'),
        })

    return JsonResponse({'success': True, 'commandes': result})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_raf_annuler_commande(request, commande_id):
    """API RAF : annule une commande PAYEE et rembobine tout."""
    from apps.pos.models import Commande
    from apps.paiements.services.annulation_service import AnnulationService

    try:
        commande = Commande.objects.select_related("point_vente").get(
            id=commande_id,
            point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
        )
        est_raf = request.user.groups.filter(name='RAF').exists()
        decision = POSAccessService.check(
            user=request.user,
            point_vente=commande.point_vente,
            action=ActionPOS.ANNULER_VENTE,
        )
        if not est_raf and not decision.allowed:
            return JsonResponse({
                'success': False,
                'error_code': decision.reason,
                'error': f"Annulation refusée ({decision.reason}).",
            }, status=403)

        commande = AnnulationService.annuler_commande(commande, request.user)
        if commande.point_vente.type == 'RESTAURATION' and commande.table_id:
            RestaurantService.liberer_table_si_terminee(commande)
        return JsonResponse({
            'success': True,
            'message': f'Commande #{commande.numero} annulée avec succès',
            'statut': commande.statut,
        })
    except Commande.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Commande introuvable'})
    except ValueError as e:
        return JsonResponse({'success': False, 'error': str(e)})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})
    
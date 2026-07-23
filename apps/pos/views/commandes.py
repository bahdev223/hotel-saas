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
from apps.hotel.models import UniteModel, LocationModel
from django.utils import timezone
from datetime import timedelta
from apps.restaurant.models import MenuModel
from apps.rh.models import Employe
from .pos import a_vue_globale_commandes, get_pv_courant_id
from ..services.caisse_session_service import get_session_ouverte_pv


def deduire_stock_commande(commande, entrepot_id=None):
    """Déduire le stock de l'entrepôt lié au point de vente.
    Si entrepot_id est fourni, déduire de celui-là précisément.
    Idempotent : une commande déjà déduite ne l'est jamais deux fois."""
    from apps.stock.models import MouvementStock
    if MouvementStock.objects.filter(
        reference=commande.numero, type_mouvement='SORTIE', motif='vente'
    ).exists():
        return

    pv = commande.point_vente
    entrepot = pv.entrepot

    if entrepot_id:
        entrepots_autorises = [entrepot_id]
    elif entrepot:
        entrepots_autorises = [entrepot.id]
    else:
        entrepots_autorises = PointVenteService.get_entrepot_ids(pv)
    if not entrepots_autorises:
        return

    for ligne in commande.lignes.all():
        if not ligne.produit:
            continue
        # Déterminer l'entrepôt à utiliser
        entrepot_cible = None
        if len(entrepots_autorises) == 1:
            eid = entrepots_autorises[0]
            entrepot_cible = Entrepot.objects.filter(id=eid).first()
        else:
            stock = StockEntrepot.objects.filter(
                produit=ligne.produit,
                entrepot_id__in=entrepots_autorises,
                quantite__gt=0
            ).first()
            if stock:
                entrepot_cible = stock.entrepot
            else:
                continue
        if not entrepot_cible:
            continue
        try:
            # Récupérer le prix unitaire pour valoriser la sortie
            se = StockEntrepot.objects.filter(
                produit=ligne.produit, entrepot=entrepot_cible
            ).first()
            valeur = float(se.prix_achat or ligne.produit.prix_achat or 0) if se else float(ligne.produit.prix_achat or 0)

            MouvementStockService.sortie_stock(
                produit=ligne.produit,
                entrepot=entrepot_cible,
                quantite=ligne.quantite,
                valeur_unitaire=valeur,
                utilisateur=commande.created_by.user.username if commande.created_by and commande.created_by.user else 'POS',
                reference=commande.numero,
                raison=f"Vente {commande.numero} - {pv.nom}"
            )
        except ValueError:
            raise


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
            commandes = Commande.objects.filter(point_vente_id=point_vente_id)
            point_vente_selected = get_object_or_404(PointVente, id=point_vente_id)
        else:
            commandes = Commande.objects.all()
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
    
    points_vente = PointVente.objects.filter(actif=True)
    
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
    """Interface dédiée à la cuisine - affiche uniquement les commandes à préparer"""
    commandes = Commande.objects.filter(
        statut__in=['EN_ATTENTE', 'EN_PREPARATION', 'PRETE']
    ).order_by('-created_at')
    
    context = {
        'commandes_attente': commandes.filter(statut='EN_ATTENTE'),
        'commandes_preparation': commandes.filter(statut='EN_PREPARATION'),
        'commandes_prete': commandes.filter(statut='PRETE'),
    }
    return render(request, 'pos/commandes/cuisine.html', context)


@login_required
def detail_commande(request, commande_id):
    """Détail d'une commande (API)"""
    commande = get_object_or_404(Commande, id=commande_id)
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
    
    commandes = Commande.objects.all().select_related('point_vente', 'facture')

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
    """Changer le statut d'une commande"""
    try:
        data = json.loads(request.body)
        commande = get_object_or_404(Commande, id=commande_id)
        nouveau_statut = data.get('statut')

        # Verrou : servir/livrer sort le stock et facture — session obligatoire
        if nouveau_statut in ('SERVIE', 'LIVREE') and not get_session_ouverte_pv(commande.point_vente):
            return JsonResponse({
                'success': False,
                'error_code': 'SESSION_REQUISE',
                'error': f"Aucune session ouverte sur {commande.point_vente.nom} — impossible de servir/livrer."
            }, status=403)

        if nouveau_statut == 'EN_PREPARATION':
            commande.passer_en_preparation()
        elif nouveau_statut == 'PRETE':
            commande.marquer_prete()
        elif nouveau_statut == 'EN_COURS_DE_LIVRAISON':
            commande.demarrer_livraison()
        elif nouveau_statut == 'SERVIE':
            commande.servir()
            deduire_stock_commande(commande, commande.entrepot_id)
            _generer_facture_commande(commande)
        elif nouveau_statut == 'LIVREE':
            commande.livrer()
            deduire_stock_commande(commande, commande.entrepot_id)
            _generer_facture_commande(commande)
        elif nouveau_statut == 'ANNULEE':
            commande.annuler()
        else:
            commande.statut = nouveau_statut
            commande.save()
        
        return JsonResponse({
            'success': True,
            'statut': commande.statut,
            'statut_display': commande.get_statut_display(),
            'message': f'Commande #{commande.numero} : {commande.get_statut_display()}'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
@transaction.atomic
def api_payer_commande(request, commande_id):
    """Payer une commande - encaisse sur la caisse choisie et marque la facture payee"""
    try:
        from ..models import Vente, LigneVente
        from apps.tresorerie.services import MouvementService
        from apps.pos.services.vente_compta_service import VenteComptaService
        from apps.facturation.services import FactureGenerators

        commande = get_object_or_404(Commande, id=commande_id)
        data = json.loads(request.body)

        if commande.vente:
            return JsonResponse({'success': False, 'error': 'Commande deja payee'})

        # CREDIT interdit pour les clients passagers
        mode_paiement = data.get('mode_paiement', 'ESPECES')
        if mode_paiement == 'CREDIT':
            from apps.clients.models import Client
            if not commande.client or commande.client_id == Client.PASSAGER_ID:
                return JsonResponse({'success': False, 'error': 'Le mode Crédit nécessite un client enregistré'}, status=400)

        # Caisse du point de vente — récupérée automatiquement, pas de choix libre
        caisse = commande.point_vente.caisse
        if not caisse or not caisse.actif:
            return JsonResponse({'success': False, 'error': f'Caisse non configurée sur {commande.point_vente.nom}'})

        employe = Employe.objects.filter(user=request.user).first()
        if not employe:
            return JsonResponse({'success': False, 'error': 'Employe non trouve'})

        session = get_session_ouverte_pv(commande.point_vente)
        if not session:
            return JsonResponse({
                'success': False,
                'error_code': 'SESSION_REQUISE',
                'error': f'Aucune session ouverte sur {caisse.nom} — ouvrez une session pour encaisser.'
            }, status=403)

        # Creer la vente
        numero = f"V{uuid.uuid4().hex[:8].upper()}"
        vente = Vente.objects.create(
            point_vente=commande.point_vente, caisse=caisse, session_caisse=session,
            numero=numero, client_nom=commande.client_nom, table=commande.table,
            mode_paiement=mode_paiement,
            caissier=session.caissier_ouverture if session else employe,
            encaisse_par=employe, montant_total=commande.montant_total, statut='PAYEE'
        )

        for ligne in commande.lignes.all():
            LigneVente.objects.create(
                vente=vente, produit=ligne.produit, menu=ligne.menu,
                quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire, notes=ligne.notes
            )

        commande.vente = vente
        commande.save()

        # Déduire le stock de l'entrepôt lié au point de vente
        from ..services.pos_service import deduire_stock_commande
        deduire_stock_commande(commande, commande.entrepot_id)

        # Encaisser sur la caisse choisie
        MouvementService.encaisser(
            caisse=caisse, montant=commande.montant_total,
            libelle=f"Paiement commande {commande.numero}",
            user=request.user, reference=commande.numero
        )

        try:
            VenteComptaService.generer_ecriture_vente(vente, request.user)
        except Exception as e:
            print(f"Erreur ecriture comptable: {e}")

        # Marquer la facture payee (creee au moment SERVIE/LIVREE)
        if hasattr(commande, 'facture') and commande.facture:
            try:
                commande.facture.marquer_payee()
            except Exception as e:
                print(f"Erreur marquage facture: {e}")
        else:
            try:
                facture = FactureGenerators.depuis_commande(commande)
                facture.emettre()
                facture.marquer_payee()
            except Exception as e:
                print(f"Erreur creation facture: {e}")

        return JsonResponse({
            'success': True, 'vente_id': vente.id, 'numero': numero,
            'montant_total': float(commande.montant_total),
            'caisse': caisse.nom, 'message': 'Paiement effectue'
        })

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
        
        point_vente = get_object_or_404(PointVente, code__iexact=data.get('point_vente_slug'))

        # Verrou : aucune commande sans session de caisse ouverte sur ce PV
        if not get_session_ouverte_pv(point_vente):
            return JsonResponse({
                'success': False,
                'error_code': 'SESSION_REQUISE',
                'error': f"Aucune session de caisse ouverte sur {point_vente.nom}. Ouvrez une session avant de commander."
            }, status=403)

        employe = Employe.objects.filter(user=request.user).first()

        # R2 : entrepôt sélectionné (ou premier disponible)
        from django.db.models import Sum
        entrepot_utilise = PointVenteService.get_entrepot_utilise(
            point_vente, data.get('entrepot_id')
        )
        for item in data.get('lignes', []):
            if item.get('type_article') == 'PRODUIT':
                produit_id = item.get('produit_id')
                if not produit_id:
                    continue
                qte = Decimal(str(item.get('quantite', 1)))
                stock_total = Decimal('0')
                if entrepot_utilise:
                    stock_total = StockEntrepot.objects.filter(
                        entrepot_id=entrepot_utilise, produit_id=produit_id
                    ).aggregate(total=Sum('quantite'))['total'] or Decimal('0')
                if stock_total < qte:
                    produit = Produit.objects.filter(id=produit_id).first()
                    nom = produit.nom if produit else 'Inconnu'
                    return JsonResponse({
                        'success': False,
                        'error': f"Stock insuffisant pour {nom} dans cet entrepôt: {float(stock_total)} disponible(s), {float(qte)} demandé(s)"
                    })

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
            type_commande=data.get('type_commande', 'SUR_PLACE'),
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
        
        for item in data.get('lignes', []):
            type_art = item.get('type_article', 'PRODUIT')
            qte = Decimal(str(item.get('quantite', 1)))
            
            if type_art == 'LOCATION':
                unite = get_object_or_404(UniteModel, id=item.get('unite_id'))
                quantite = int(item.get('heures', 1))
                type_tarif = item.get('type_tarif', 'HEURE')
                now = timezone.localtime()
                if type_tarif == 'JOUR':
                    prix = Decimal(str(item.get('prix', unite.prix_jour or unite.prix)))
                    date_fin = now + timedelta(days=quantite)
                else:
                    prix = Decimal(str(item.get('prix', unite.prix)))
                    date_fin = now + timedelta(hours=quantite)

                montant_ligne = Decimal(str(item.get('total', 0))) or (prix * Decimal(str(quantite)))

                location = LocationModel.objects.create(
                    client=client_obj or Client.get_passager(),
                    unite=unite,
                    type_location=unite.type_unite or 'CHAMBRE',
                    type_tarif=type_tarif,
                    date_debut=now,
                    date_fin=date_fin,
                    montant_total=montant_ligne,
                    notes=data.get('notes', ''),
                )
                
                LigneCommande.objects.create(
                    commande=commande, unite=unite,
                    heures=quantite, quantite=1, prix_unitaire=prix
                )
                total += montant_ligne
            elif type_art == 'MENU':
                menu = get_object_or_404(MenuModel, id=item.get('menu_id'), actif=True)
                prix = Decimal(str(menu.prix_vente))
                LigneCommande.objects.create(commande=commande, menu=menu, quantite=qte, prix_unitaire=prix)
                total += qte * prix
            else:
                produit = get_object_or_404(Produit, id=item.get('produit_id'), actif=True)
                prix = Decimal(str(produit.prix_vente))
                LigneCommande.objects.create(commande=commande, produit=produit, quantite=qte, prix_unitaire=prix)
                total += qte * prix
        
        commande.montant_total = total + commande.frais_livraison
        commande.save()
        
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
            'message': 'Commande créée avec succès'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_vente_recu(request, vente_id):
    """API : retourne les données d'une vente pour réimpression du ticket"""
    from ..models import Vente
    v = get_object_or_404(Vente, id=vente_id)
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

    if not request.user.groups.filter(name='RAF').exists():
        return JsonResponse({'success': False, 'error': 'Accès refusé. Réservé au RAF.'})

    try:
        commande = Commande.objects.get(id=commande_id)
        commande = AnnulationService.annuler_commande(commande, request.user)
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
    
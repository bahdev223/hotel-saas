# apps/hotel/views/api.py
import json
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from django.views.decorators.csrf import csrf_exempt

from apps.clients.models import Client
from ..models import LocationModel, UniteModel


def _payload(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return {}


def _money(value):
    return float(value or Decimal("0"))


def _get_or_create_location_client(data):
    client_id = data.get("client_id")
    if client_id:
        return get_object_or_404(Client, id=client_id)

    nom = (data.get("client_nom") or "").strip()
    prenom = (data.get("client_prenom") or "").strip()
    telephone = (data.get("client_telephone") or "").strip()
    email = (data.get("client_email") or "").strip()

    if not nom and not prenom and not telephone and not email:
        return Client.get_passager()

    return Client.objects.create(
        nom=nom or "Client",
        prenom=prenom or "Passager",
        telephone=telephone or f"PASSAGER-{timezone.now().strftime('%Y%m%d%H%M%S')}",
        email=email or None,
    )


# apps/hotel/views/api.py - CORRIGER la fonction api_stats

@login_required
@require_GET
def api_stats(request):
    total_unites = UniteModel.objects.filter(actif=True).count()
    unites_disponibles = UniteModel.objects.filter(actif=True, statut="DISPONIBLE").count()
    unites_occupees = UniteModel.objects.filter(actif=True, statut="OCCUPEE").count()
    taux_occupation = round((unites_occupees / total_unites * 100), 1) if total_unites else 0
    
    # 🔥 CORRECTION: utiliser les lignes de facture pour calculer le CA
    from apps.facturation.models import LigneFactureModel
    from datetime import date
    
    mois_courant = date.today().month
    annee_courante = date.today().year
    
    # Récupérer le CA via les lignes de facture (plus fiable)
    lignes_mois = LigneFactureModel.objects.filter(
        facture__date_emission__year=annee_courante,
        facture__date_emission__month=mois_courant,
        facture__statut='PAYEE'
    )
    
    ca_mois = sum(l.total_ttc for l in lignes_mois)

    locations_en_cours = LocationModel.objects.filter(statut='CONFIRMEE').count()

    return JsonResponse({
        "success": True,
        "stats": {
            "total_unites": total_unites,
            "unites_disponibles": unites_disponibles,
            "unites_occupees": unites_occupees,
            "taux_occupation": taux_occupation,
            "locations_en_cours": locations_en_cours,
            "ca_mois": float(ca_mois),
        },
    })
@login_required
@require_GET
def api_clients(request):
    clients = Client.objects.filter(statut='ACTIF').order_by("nom", "prenom")
    return JsonResponse({
        "success": True,
        "clients": [
            {
                "id": client.id,
                "nom": client.nom,
                "prenom": client.prenom,
                "telephone": client.telephone,
                "email": client.email or "",
                "adresse": client.adresse or "",
            }
            for client in clients
        ],
    })


@login_required
@require_GET
def api_unites(request):
    unites = UniteModel.objects.filter(actif=True).order_by("type_unite", "code")
    return JsonResponse({
        "success": True,
        "unites": [
            {
                "id": unite.id,
                "code": unite.code,
                "nom": unite.nom,
                "type_unite": unite.type_unite,
                "type_display": unite.get_type_unite_display(),
                "capacite": unite.capacite,
                "prix": _money(unite.prix),
                "statut": unite.statut,
                "image": unite.image.url if unite.image else None,
            }
            for unite in unites
        ],
    })


@login_required
@require_GET
def api_locations(request):
    locations = LocationModel.objects.select_related("client", "unite").order_by("-date_debut")
    statut = request.GET.get('statut')
    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    if statut:
        locations = locations.filter(statut=statut)
    if date_debut:
        locations = locations.filter(date_debut__date__gte=date_debut)
    if date_fin:
        locations = locations.filter(date_debut__date__lte=date_fin)
    locations = locations[:200]
    
    result = []
    for location in locations:
        # Récupérer les infos de paiement depuis la facture
        reste_a_payer = location.montant_total
        montant_paye = Decimal('0')
        
        if hasattr(location, 'facture') and location.facture:
            reste_a_payer = location.facture.reste_a_payer
            montant_paye = location.facture.total_paye
        
        result.append({
            "id": location.id,
            "client_nom": location.client_nom or location.client.nom_complet,
            "client_telephone": location.client_telephone or location.client.telephone or "",
            "unite_nom": f"{location.unite.code} - {location.unite.nom}",
            "type": location.type_location,
            "type_display": location.get_type_location_display(),
            "date_debut": location.date_debut.isoformat(),
            "date_fin": location.date_fin.isoformat(),
            "duree_heures": location.duree_heures,
            "duree_display": location.duree_display,
            "montant_total": _money(location.montant_total),
            "montant_avance": _money(location.montant_avance),
            "montant_paye": _money(montant_paye),
            "reste_a_payer": _money(reste_a_payer),
            "statut": location.statut,
        })
    
    return JsonResponse({"success": True, "locations": result})


@login_required
@require_POST
def api_save_client(request):
    data = _payload(request)
    try:
        client = Client.objects.create(
            nom=data.get("nom", "").strip(),
            prenom=data.get("prenom", "").strip(),
            telephone=data.get("telephone", "").strip(),
            email=data.get("email") or None,
            adresse=data.get("adresse") or None,
        )
        return JsonResponse({"success": True, "id": client.id})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@require_POST
def api_save_unite(request):
    data = _payload(request)
    try:
        type_unite = data.get("type_unite") or "CHAMBRE"
        if type_unite not in ("CHAMBRE", "VIP"):
            return JsonResponse({"success": False, "error": "Type d'unité invalide. Choisir CHAMBRE ou VIP."}, status=400)
        unite = UniteModel.objects.create(
            code=data.get("code", "").strip(),
            nom=data.get("nom", "").strip(),
            type_unite=type_unite,
            capacite=int(data.get("capacite") or 1),
            prix=Decimal(str(data.get("prix") or 0)),
            prix_jour=Decimal(str(data.get("prix_jour") or 0)),
        )
        return JsonResponse({"success": True, "id": unite.id})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@require_POST
def api_supprimer_unite(request, unite_id):
    try:
        unite = get_object_or_404(UniteModel, id=unite_id)
        unite.delete()
        return JsonResponse({"success": True})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@require_POST
def api_save_location(request):
    data = _payload(request)
    try:
        unite = get_object_or_404(UniteModel, id=data.get("element_id") or data.get("unite_id"))
        type_location = data.get("type") or data.get("type_location", "CHAMBRE")

        from datetime import datetime
        date_debut_str = data.get("date_debut")
        date_fin_str = data.get("date_fin")
        if not date_debut_str or not date_fin_str:
            return JsonResponse({"success": False, "error": "Dates requises"}, status=400)

        date_debut = datetime.fromisoformat(date_debut_str)
        date_fin = datetime.fromisoformat(date_fin_str)

        # Client passager automatique
        client = Client.get_passager()
        client_nom = (data.get("client_nom") or "").strip()
        client_telephone = (data.get("client_telephone") or "").strip()

        montant_avance = Decimal(str(data.get("montant_avance") or 0))

        unite.occuper()

        type_tarif = data.get("type_tarif", "HEURE")
        if type_tarif not in ["HEURE", "JOUR"]:
            type_tarif = "HEURE"

        location = LocationModel.objects.create(
            client=client,
            unite=unite,
            type_location=type_location,
            type_tarif=type_tarif,
            date_debut=date_debut,
            date_fin=date_fin,
            montant_avance=montant_avance,
            notes=data.get("notes") or "",
            client_nom=client_nom,
            client_telephone=client_telephone,
        )

        location.calculer_montant_total()

        return JsonResponse({"success": True, "id": location.id})
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@require_POST
def api_paiement_location(request, location_id):
    """Enregistrer un paiement via apps.paiements (lié à la facture)"""
    from django.contrib.contenttypes.models import ContentType
    from apps.paiements.models import Paiement
    from apps.facturation.services import FactureActions, FactureGenerators
    from apps.rh.models import Employe
    from apps.tresorerie.models import Caisse
    
    data = _payload(request)
    location = get_object_or_404(LocationModel, id=location_id)
    
    try:
        montant = Decimal(str(data.get("montant") or 0))
        mode = data.get("mode", "ESPECES")
        caisse_id = data.get("caisse_id")
        
        if montant <= 0:
            return JsonResponse({"success": False, "error": "Montant invalide"}, status=400)
        
        # 🔥 1. S'assurer que la facture existe
        if not hasattr(location, 'facture') or not location.facture:
            facture = FactureGenerators.depuis_location(location)
            facture.emettre()
        else:
            facture = location.facture
        
        # 🔥 2. Vérifier le reste à payer
        if montant > facture.reste_a_payer:
            return JsonResponse({
                "success": False, 
                "error": f"Montant trop élevé. Reste à payer: {facture.reste_a_payer:,.0f} F"
            }, status=400)
        
        # 🔥 3. Récupérer l'employé connecté
        employe = Employe.objects.filter(user=request.user).first()
        if not employe:
            return JsonResponse({"success": False, "error": "Employé non trouvé"}, status=400)
        
        # 🔥 4. Récupérer la caisse (optionnelle)
        caisse = None
        if caisse_id:
            caisse = get_object_or_404(Caisse, id=caisse_id)
        
        # 🔥 5. Créer le paiement lié à la FACTURE (pas à la location)
        content_type = ContentType.objects.get_for_model(facture)
        
        paiement = Paiement.objects.create(
            reference=f"PAY-{timezone.now().strftime('%y%m%d%H%M%S')}",
            type_paiement='VENTE',
            montant=montant,
            sens='ENTREE',
            mode=mode,
            caisse=caisse,
            content_type=content_type,
            object_id=facture.id,
            created_by=request.user,
            notes=data.get("notes", ""),
            statut='VALIDE'
        )
        
        # 🔥 6. Valider le paiement (crée le mouvement de caisse)
        paiement.valider(request.user)
        
        # 🔥 7. Mettre à jour le statut de la facture
        FactureActions.verifier_et_mettre_a_jour_statut(facture)
        
        return JsonResponse({
            "success": True,
            "message": f"Paiement de {montant:,.0f} F enregistré",
            "reste_a_payer": float(facture.reste_a_payer),
            "total_paye": float(facture.total_paye),
            "est_payee": facture.est_payee
        })
        
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
@csrf_exempt
@require_POST
def api_checkout_location(request, location_id):
    location = get_object_or_404(LocationModel, id=location_id)
    location.terminer_auto()
    return JsonResponse({"success": True})


@login_required
@require_POST
def api_annuler_location(request, location_id):
    location = get_object_or_404(LocationModel, id=location_id)
    location.annuler()
    return JsonResponse({"success": True})


@login_required
@require_GET
def api_ca_evolution(request):
    from django.db.models import Sum
    from apps.facturation.models import LigneFactureModel
    from datetime import date, timedelta

    data = []
    for i in range(29, -1, -1):
        jour = date.today() - timedelta(days=i)
        ca = LigneFactureModel.objects.filter(
            facture__date_emission=jour,
            facture__statut='PAYEE'
        ).aggregate(total=Sum('total_ttc'))['total'] or 0
        data.append({'date': jour.strftime('%d/%m'), 'ca': float(ca)})
    return JsonResponse({'success': True, 'data': data})


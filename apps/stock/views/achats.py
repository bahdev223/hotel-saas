# apps/stock/views/achats.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
from datetime import date, timedelta
from decimal import Decimal
import json
import uuid

from ..models import BonEntree, LigneBonEntree, Produit, Entrepot, Domaine
from ..services import MouvementStockService, AchatService
from apps.fournisseurs.models import Fournisseur, EcheanceFournisseur
from apps.facturation.models import FactureModel, LigneFactureModel
from apps.tresorerie.models import Caisse
from apps.tresorerie.services import MouvementService


@login_required
def liste_achats(request):
    """Page de gestion des achats"""
    fournisseurs = Fournisseur.objects.filter(actif=True)
    entrepots = Entrepot.objects.filter(actif=True)

    caisses = Caisse.objects.filter(actif=True)
    domaines_list = Domaine.objects.filter(actif=True)

    context = {
        'titre': 'Achats (ASAR)',
        'fournisseurs': fournisseurs,
        'entrepots': entrepots,
        'domaines': domaines_list,
        'caisses': caisses,
        'fournisseurs_json': json.dumps([{'id': f.id, 'nom': f.nom, 'code': f.code} for f in fournisseurs], ensure_ascii=False),
        'entrepots_json': json.dumps([{'id': e.id, 'nom': e.nom, 'code': e.code, 'type': e.type_entrepot} for e in entrepots], ensure_ascii=False),
        'caisses_json': json.dumps([{'id': c.id, 'nom': c.nom, 'code': c.code, 'type': c.type_financier, 'solde': float(c.solde)} for c in caisses], ensure_ascii=False),
    }
    return render(request, 'stock/achats/liste.html', context)


@login_required
@require_http_methods(["GET"])
def api_liste_achats(request):
    """API liste des achats"""
    achats = BonEntree.objects.all().select_related('fournisseur', 'entrepot')

    date_debut = request.GET.get('date_debut')
    date_fin = request.GET.get('date_fin')
    fournisseur_id = request.GET.get('fournisseur_id')
    entrepot_id = request.GET.get('entrepot_id')

    if date_debut:
        achats = achats.filter(date_reception__date__gte=date_debut)
    if date_fin:
        achats = achats.filter(date_reception__date__lte=date_fin)
    if fournisseur_id:
        achats = achats.filter(fournisseur_id=fournisseur_id)
    if entrepot_id:
        achats = achats.filter(entrepot_id=entrepot_id)

    achats = achats.order_by('-date_reception')[:100]

    data = []
    for a in achats:
        data.append({
            'id': a.id,
            'numero': a.numero,
            'reference_fournisseur': a.reference_fournisseur,
            'fournisseur': a.fournisseur.nom if a.fournisseur else '',
            'fournisseur_id': str(a.fournisseur.id) if a.fournisseur else None,
            'entrepot': a.entrepot.nom if a.entrepot else '',
            'date_reception': a.date_reception.isoformat() if a.date_reception else '',
            'total': float(a.total),
            'statut': a.statut,
            'lignes_count': a.lignes.count(),
            'notes': a.notes or '',
        })
    return JsonResponse({'success': True, 'achats': data})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_creer_achat(request):
    """Crée un achat (ASAR) complet : commande + réception + facture + paiement.

    Utilise AchatService pour la cohérence, puis crée la facture,
    le paiement ou l'échéance selon le mode.
    """
    try:
        if request.content_type and 'multipart' in request.content_type:
            data = request.POST.dict()
            fichier_image = request.FILES.get('image')
        else:
            data = json.loads(request.body)
            fichier_image = None

        fournisseur_id = data.get('fournisseur_id')
        entrepot_id = data.get('entrepot_id')
        reference_fournisseur = data.get('reference_fournisseur', '')
        date_achat = data.get('date_achat', date.today().isoformat())
        mode_paiement = data.get('mode_paiement', 'CREDIT')
        notes = data.get('notes', '')
        echeance_jours = int(data.get('echeance_jours', 30))
        lignes_data = json.loads(data.get('lignes', '[]')) if isinstance(data.get('lignes'), str) else data.get('lignes', [])

        if not fournisseur_id or not lignes_data:
            return JsonResponse({'success': False, 'error': 'Fournisseur et lignes requis'})

        fournisseur = Fournisseur.objects.get(id=fournisseur_id)
        entrepot = Entrepot.objects.get(id=entrepot_id) if entrepot_id else Entrepot.objects.filter(type_entrepot='CENTRAL', actif=True).first()
        if not entrepot:
            return JsonResponse({'success': False, 'error': 'Aucun entrepôt disponible'})

        with transaction.atomic():
            # 1. Créer la commande + réception via AchatService
            bon = AchatService.creer_commande(
                fournisseur=fournisseur,
                lignes_data=lignes_data,
                entrepot=entrepot,
                reference_fournisseur=reference_fournisseur,
                notes=notes,
                user=request.user,
                date_commande=date_achat,
            )

            # 2. Réception totale immédiate
            lignes_recues = [
                {'ligne_id': l.id, 'quantite_recue': l.quantite_commandee}
                for l in bon.lignes.all()
            ]
            AchatService.enregistrer_reception(bon, lignes_recues, user=request.user)

            total = bon.total

            # 3. Créer la Facture fournisseur liée
            facture = FactureModel.objects.create(
                type='FOURNISSEUR',
                fournisseur=fournisseur,
                client_nom=fournisseur.nom,
                client_contact=fournisseur.telephone or '',
                numero=f"A-{bon.numero}",
                bon_entree=bon,
                notes=f"ASAR - {reference_fournisseur}",
                statut='EMISE',
            )
            if fichier_image:
                facture.image = fichier_image
                facture.save()

            LigneFactureModel.objects.create(
                facture=facture,
                description=f"Achat {fournisseur.nom} - {reference_fournisseur or bon.numero}",
                quantite=1,
                prix_unitaire=total,
                tva=0,
            )

            # 4. Paiement ou échéance
            paiement_info = None
            solde_info = None
            echeance = None

            if mode_paiement != 'CREDIT':
                caisse_id = data.get('caisse_id')
                caisse = None
                if caisse_id:
                    caisse = Caisse.objects.filter(id=caisse_id, actif=True).first()
                if not caisse:
                    caisse = Caisse.objects.filter(type_financier='ESPECES', role='CENTRALE', actif=True).first()
                if caisse:
                    MouvementService.decaisser(
                        caisse=caisse,
                        montant=total,
                        libelle=f"ASAR {bon.numero} - {fournisseur.nom}",
                        user=request.user,
                        reference=bon.numero,
                        source=bon,
                    )
                    paiement_info = {
                        'montant': float(total),
                        'mode': mode_paiement,
                        'caisse': caisse.nom,
                    }
                facture.marquer_payee()
            else:
                # Crédit : créer échéance + mettre à jour solde
                echeance = EcheanceFournisseur.objects.create(
                    fournisseur=fournisseur,
                    facture=facture,
                    bon_entree=bon,
                    montant=total,
                    date_echeance=date.today() + timedelta(days=echeance_jours),
                )
                try:
                    from apps.comptabilite.models import CompteFournisseur, ExerciceModel
                    exercice = ExerciceModel.objects.filter(cloture=False).first()
                    if exercice:
                        ct, _ = CompteFournisseur.objects.get_or_create(
                            fournisseur=fournisseur,
                            exercice=exercice,
                            defaults={'solde': 0}
                        )
                        ct.solde += float(total)
                        ct.save()
                        solde_info = {
                            'fournisseur': fournisseur.nom,
                            'nouveau_solde': float(ct.solde),
                        }
                except Exception:
                    pass

            return JsonResponse({
                'success': True,
                'facture_id': facture.id,
                'achat': {
                    'id': bon.id,
                    'numero': bon.numero,
                    'reference_fournisseur': bon.reference_fournisseur,
                    'fournisseur': fournisseur.nom,
                    'total': float(bon.total),
                    'statut': bon.statut,
                },
                'paiement': paiement_info,
                'solde_fournisseur': solde_info,
                'echeance_id': echeance.id if echeance else None,
            })

    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_enregistrer_reception(request, bon_id):
    """Enregistre une réception partielle sur un bon d'entrée existant."""
    try:
        data = json.loads(request.body)
        bon = get_object_or_404(BonEntree, id=bon_id)

        lignes_recues = data.get('lignes', [])
        if not lignes_recues:
            return JsonResponse({'success': False, 'error': 'Aucune ligne de réception'})

        bon = AchatService.enregistrer_reception(bon, lignes_recues, user=request.user)

        return JsonResponse({
            'success': True,
            'bon_id': bon.id,
            'statut': bon.statut,
            'total': float(bon.total),
            'message': f"Réception enregistrée — statut: {bon.get_statut_display()}",
        })

    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

# apps/stock/views/achats.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.db import transaction
from django.utils import timezone
from datetime import date
from decimal import Decimal
import json
import uuid

from ..models import BonEntree, LigneBonEntree, Produit, Entrepot, Domaine
from ..services import MouvementStockService
from apps.fournisseurs.models import Fournisseur
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
    """Crée un achat (ASAR) : BonEntree + Facture fournisseur + MouvementStock + Paiement"""
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
        lignes_data = json.loads(data.get('lignes', '[]')) if isinstance(data.get('lignes'), str) else data.get('lignes', [])

        if not fournisseur_id or not lignes_data:
            return JsonResponse({'success': False, 'error': 'Fournisseur et lignes requis'})

        fournisseur = Fournisseur.objects.get(id=fournisseur_id)
        entrepot = Entrepot.objects.get(id=entrepot_id) if entrepot_id else Entrepot.objects.filter(type_entrepot='CENTRAL').first()
        if not entrepot:
            return JsonResponse({'success': False, 'error': 'Aucun entrepôt disponible'})

        with transaction.atomic():
            bon = BonEntree.objects.create(
                fournisseur=fournisseur,
                entrepot=entrepot,
                reference_fournisseur=reference_fournisseur,
                date_reception=date_achat,
                notes=notes,
                statut='VALIDE',
                created_by=request.user,
                valide_by=request.user,
            )

            total = Decimal('0')

            for ligne_data in lignes_data:
                produit_id = ligne_data.get('produit_id')
                quantite = Decimal(str(ligne_data.get('quantite', 1)))
                prix_achat = Decimal(str(ligne_data.get('prix_achat', 0)))
                prix_vente = ligne_data.get('prix_vente')

                if quantite <= 0 or prix_achat <= 0:
                    continue

                produit = Produit.objects.get(id=produit_id)

                LigneBonEntree.objects.create(
                    bon_entree=bon,
                    produit=produit,
                    quantite_commandee=quantite,
                    quantite_recue=quantite,
                    prix_achat=prix_achat,
                )
                montant_ligne = quantite * prix_achat
                total += montant_ligne

                MouvementStockService.entree_stock(
                    produit=produit,
                    entrepot=entrepot,
                    quantite=quantite,
                    utilisateur=request.user.username,
                    motif='achat',
                    valeur_unitaire=float(prix_achat),
                    reference=bon.numero,
                    raison=f"Achat {fournisseur.nom} - {reference_fournisseur}"
                )

                champs_maj = {'prix_achat': prix_achat}
                if prix_vente is not None:
                    champs_maj['prix_vente'] = Decimal(str(prix_vente))
                Produit.objects.filter(id=produit_id).update(**champs_maj)

            bon.total = total
            bon.save()

            # Créer la Facture fournisseur liée
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

            # Ligne de facture récapitulative
            LigneFactureModel.objects.create(
                facture=facture,
                description=f"Achat {fournisseur.nom} - {reference_fournisseur or bon.numero}",
                quantite=1,
                prix_unitaire=total,
                tva=0,
            )

            # Paiement
            paiement_info = None
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

            # Crédit fournisseur
            solde_info = None
            if mode_paiement == 'CREDIT':
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

            facture.marquer_payee()

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
            })

    except Exception as e:
        import traceback; traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

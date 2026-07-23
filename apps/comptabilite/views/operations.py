# apps/comptabilite/views/operations.py (version corrigée)
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
import json

from apps.paiements.models import Paiement
from apps.facturation.models import FactureModel, LigneFactureModel
from apps.tresorerie.models import Caisse
from apps.rh.models import Employe
from apps.comptabilite.services import EcritureComptableService
from apps.clients.models import Client
from apps.fournisseurs.models import Fournisseur
from apps.comptabilite.models import CompteClient, CompteFournisseur, ExerciceModel, TiersModel, CompteModel
from apps.comptabilite.data.categories_depense import CATEGORIES_DEPENSE


class BaseOperation:
    """Classe de base pour toutes les opérations"""
    
    def __init__(self, request):
        self.request = request
        self.user = request.user
    
    def get_employe(self):
        return Employe.objects.filter(user=self.user).first()
    
    def get_caisse(self, caisse_id=None):
        if caisse_id:
            return Caisse.objects.filter(id=caisse_id).first()
        return Caisse.objects.filter(actif=True).first()
    
    def success_response(self, message, redirect_url):
        messages.success(self.request, message)
        return redirect(redirect_url)
    
    def error_response(self, message, redirect_url):
        messages.error(self.request, message)
        return redirect(redirect_url)


class AchatOperation(BaseOperation):
    """Opération d'achat fournisseur"""
    
    def sauvegarder(self, data):
        montant_ht = Decimal(data.get('montant_ht', 0))
        tva = Decimal(data.get('tva', 18))
        montant_ttc = Decimal(data.get('montant_ttc', 0))
        montant_tva = montant_ttc - montant_ht
        
        # Créer la facture fournisseur
        facture = FactureModel.objects.create(
            client_nom=data.get('fournisseur'),
            notes=f"Achat fournisseur - {data.get('reference_fournisseur', '')}",
            statut='EMISE'
        )
        
        # Ligne de facture
        LigneFactureModel.objects.create(
            facture=facture,
            description=data.get('description', 'Achat'),
            quantite=1,
            prix_unitaire=montant_ht,
            tva=tva
        )
        
        # Créer le paiement (dette)
        paiement = Paiement.objects.create(
            reference=f"ACHAT-{facture.numero}",
            type_paiement='ACHAT',
            montant=montant_ttc,
            sens='SORTIE',
            mode=data.get('mode_paiement', 'ESPECES'),
            caisse=self.get_caisse(data.get('caisse_id')),
            objet=facture,
            statut='VALIDE',
            created_by=self.user,
            notes=data.get('notes', '')
        )
        
        # Ecriture comptable (si compte charge fourni)
        compte_charge = data.get('compte_charge')
        if compte_charge:
            EcritureComptableService.creer_ecriture_achat(
                montant_ttc=montant_ttc,
                montant_tva=montant_tva,
                montant_ht=montant_ht,
                libelle=f"Achat {data.get('fournisseur', '')} - {data.get('description', '')}",
                compte_charge=compte_charge,
                compte_fournisseur='401',
                compte_tva='443' if montant_tva > 0 else None,
                user=self.user,
            )
        
        return paiement


class VenteOperation(BaseOperation):
    """Opération de vente client"""
    
    def sauvegarder(self, data):
        montant_ttc = Decimal(data.get('montant_ttc', 0))
        tva = Decimal(data.get('tva', 18))
        montant_tva = montant_ttc * tva / (Decimal('100') + tva) if tva else Decimal('0')
        montant_ht = montant_ttc - montant_tva
        
        # Créer la facture client
        facture = FactureModel.objects.create(
            client_nom=data.get('client'),
            notes=f"Vente client - {data.get('reference_client', '')}",
            statut='PAYEE'
        )
        
        # Ligne de facture
        LigneFactureModel.objects.create(
            facture=facture,
            description=data.get('description', 'Vente'),
            quantite=1,
            prix_unitaire=montant_ht,
            tva=tva
        )
        
        # Créer le paiement (encaissement)
        caisse = self.get_caisse(data.get('caisse_id'))
        paiement = Paiement.objects.create(
            reference=f"VENTE-{facture.numero}",
            type_paiement='VENTE',
            montant=montant_ttc,
            sens='ENTREE',
            mode=data.get('mode_paiement', 'ESPECES'),
            caisse=caisse,
            objet=facture,
            statut='VALIDE',
            created_by=self.user,
            notes=data.get('notes', '')
        )
        
        # Ecriture comptable
        EcritureComptableService.creer_ecriture_vente(
            caisse=caisse,
            montant=montant_ttc,
            libelle=f"Vente {data.get('client', '')} - {data.get('description', '')}",
            compte_produit_code='706',
            user=self.user,
        )
        
        return paiement


class DepenseOperation(BaseOperation):
    """Opération de dépense avec écriture comptable"""
    
    def sauvegarder(self, data):
        montant = Decimal(data.get('montant', 0))
        date_operation = data.get('date_operation', date.today())
        description = data.get('description', '')
        beneficiaire = data.get('beneficiaire', '')
        mode = data.get('mode_paiement', 'ESPECES')
        caisse = self.get_caisse(data.get('caisse_id'))
        notes = data.get('notes', '')
        compte_charge_id = data.get('compte_charge_id')
        
        # 1. Créer le paiement (sortie)
        paiement = Paiement.objects.create(
            reference=f"DEP-{date.today().strftime('%Y%m%d%H%M%S')}",
            type_paiement='DEPENSE',
            montant=montant,
            sens='SORTIE',
            mode=mode,
            caisse=caisse,
            statut='VALIDE',
            created_by=self.user,
            notes=f"{description}\nBénéficiaire: {beneficiaire}\n{notes}".strip()
        )
        
        # 2. Ecriture comptable via le service central
        EcritureComptableService.creer_ecriture_charge(
            caisse=caisse,
            montant=montant,
            libelle=description or 'Sans motif',
            compte_charge=compte_charge_id or '658',
            beneficiaire=beneficiaire,
            date_operation=date_operation,
            user=self.user,
        )
        
        return paiement


class RecetteOperation(BaseOperation):
    """Opération de recette avec écriture comptable"""
    
    def sauvegarder(self, data):
        montant = Decimal(data.get('montant', 0))
        mode = data.get('mode_paiement', 'ESPECES')
        caisse = self.get_caisse(data.get('caisse_id'))
        description = data.get('description', '')
        
        # 1. Créer le paiement (entrée)
        paiement = Paiement.objects.create(
            reference=f"REC-{date.today().strftime('%Y%m%d%H%M%S')}",
            type_paiement='RECETTE',
            montant=montant,
            sens='ENTREE',
            mode=mode,
            caisse=caisse,
            statut='VALIDE',
            created_by=self.user,
            notes=data.get('notes', '')
        )
        
        # 2. Ecriture comptable via le service central
        EcritureComptableService.creer_ecriture_vente(
            caisse=caisse,
            montant=montant,
            libelle=f"Recette: {description or 'Sans motif'}",
            compte_produit_code='706',
            user=self.user,
        )
        
        return paiement


# ==================== HELPERS ====================

def _get_or_create_compte(code, libelle):
    """Ensure a CompteModel exists for the given code"""
    compte, _ = CompteModel.objects.get_or_create(
        code=code,
        defaults={'libelle': libelle, 'type_compte': 'TIERS', 'actif': True}
    )
    return compte


def _resolve_tiers_client(client):
    """Resolve a Client to a TiersModel for accounting"""
    compte = _get_or_create_compte('411', 'Clients')
    tiers, _ = TiersModel.objects.get_or_create(
        code=f"CLI-{client.id}",
        defaults={
            'nom': client.nom_complet,
            'type_tiers': 'CLIENT',
            'compte': compte,
            'telephone': client.telephone or '',
            'email': client.email or '',
            'adresse': client.adresse or '',
        }
    )
    return tiers


def _resolve_tiers_fournisseur(fournisseur):
    """Resolve a Fournisseur to a TiersModel for accounting"""
    compte = _get_or_create_compte('401', 'Fournisseurs')
    tiers, _ = TiersModel.objects.get_or_create(
        code=f"FRN-{fournisseur.id}",
        defaults={
            'nom': fournisseur.nom,
            'type_tiers': 'FOURNISSEUR',
            'compte': compte,
            'telephone': fournisseur.telephone or '',
            'email': fournisseur.email or '',
            'adresse': fournisseur.adresse or '',
        }
    )
    return tiers


def _get_clients_soldes():
    """Build a dict {client_id: solde} for all active clients"""
    from datetime import date
    exercice = EcritureComptableService._get_exercice(date.today())
    comptes = CompteClient.objects.filter(exercice=exercice).select_related('client')
    return {c.client_id: float(c.solde) for c in comptes}


# ==================== VUES ====================

@login_required
def liste_operations(request):
    """Liste de toutes les opérations (paiements)"""
    from django.db.models import Q

    domaine = request.GET.get('domaine', '').strip()

    DOMAINE_MAP = {
        'brasserie': ['BAR', 'VIP', 'TERRASSE', 'GUICHET'],
        'restaurant': ['RESTAURANT', 'ROOM_SERVICE'],
        'hotel': ['RECEPTION'],
    }

    paiements = Paiement.objects.filter(
        type_paiement__in=['DEPENSE', 'RECETTE', 'DEPOT', 'REMBOURSEMENT']
    ).select_related('caisse__point_vente').order_by('-date')

    if domaine and domaine in DOMAINE_MAP:
        paiements = paiements.filter(
            caisse__point_vente__emplacement__in=DOMAINE_MAP[domaine]
        )

    operations = []
    for p in paiements:
        emp = p.caisse.point_vente.emplacement if p.caisse and p.caisse.point_vente else None
        op_domaine = next((d for d, emps in DOMAINE_MAP.items() if emp in emps), '')
        operations.append({
            'id': p.id,
            'type': p.type_paiement.lower(),
            'type_display': p.get_type_paiement_display(),
            'reference': p.reference,
            'date': p.date,
            'montant': p.montant,
            'sens': p.sens,
            'mode': p.mode,
            'statut': p.statut,
            'notes': p.notes,
            'domaine': op_domaine,
        })
    
    context = {
        'operations': operations,
        'total_operations': len(operations),
        'total_entrees': sum(o['montant'] for o in operations if o['sens'] == 'ENTREE'),
        'total_sorties': sum(o['montant'] for o in operations if o['sens'] == 'SORTIE'),
        'caisses': Caisse.objects.filter(actif=True),
        'clients': Client.objects.filter(statut='ACTIF').order_by('nom', 'prenom'),
        'fournisseurs': Fournisseur.objects.filter(actif=True).order_by('nom'),
        'modes_paiement': Paiement.MODE_CHOICES,
        'taux_tva': [0, 5.5, 10, 18, 20],
        'today': date.today(),
        'client_soldes': _get_clients_soldes(),
        'categories_depense': CATEGORIES_DEPENSE,
    }
    return render(request, 'comptabilite/operations/liste.html', context)


@login_required
def creer_achat(request):
    """Formulaire et traitement d'achat"""
    if request.method == 'POST':
        try:
            data = {
                'fournisseur': request.POST.get('fournisseur_nom'),
                'reference_fournisseur': request.POST.get('numero_facture'),
                'montant_ht': Decimal(request.POST.get('montant_ht', 0)),
                'tva': Decimal(request.POST.get('taux_tva', 18)),
                'montant_ttc': Decimal(request.POST.get('montant_ttc', 0)),
                'mode_paiement': request.POST.get('mode_paiement', 'ESPECES'),
                'caisse_id': request.POST.get('caisse_id'),
                'description': request.POST.get('description', ''),
                'notes': request.POST.get('notes', ''),
            }
            
            operation = AchatOperation(request)
            result = operation.sauvegarder(data)
            
            messages.success(request, f"Achat créé avec succès - Réf: {result.reference}")
            return redirect('comptabilite:operations')
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
    
    # GET: Formulaire
    context = {
        'caisses': Caisse.objects.filter(actif=True),
        'modes_paiement': Paiement.MODE_CHOICES,  # 🔥 CORRIGÉ: MODE_CHOICES au lieu de MODE_PAIEMENT_CHOICES
        'taux_tva': [0, 5.5, 10, 18, 20],
        'title': 'Nouvel achat',
    }
    return render(request, 'comptabilite/operations/achat.html', context)


@login_required
def creer_vente(request):
    """Formulaire et traitement de vente"""
    if request.method == 'POST':
        try:
            data = {
                'client': request.POST.get('client_nom'),
                'reference_client': request.POST.get('numero_facture'),
                'montant_ttc': Decimal(request.POST.get('montant_ttc', 0)),
                'tva': Decimal(request.POST.get('taux_tva', 18)),
                'mode_paiement': request.POST.get('mode_paiement', 'ESPECES'),
                'caisse_id': request.POST.get('caisse_id'),
                'description': request.POST.get('description', ''),
                'notes': request.POST.get('notes', ''),
            }
            
            operation = VenteOperation(request)
            result = operation.sauvegarder(data)
            
            messages.success(request, f"Vente créée avec succès - Réf: {result.reference}")
            return redirect('comptabilite:operations')
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'caisses': Caisse.objects.filter(actif=True),
        'modes_paiement': Paiement.MODE_CHOICES,  # 🔥 CORRIGÉ
        'taux_tva': [0, 5.5, 10, 18, 20],
        'title': 'Nouvelle vente',
    }
    return render(request, 'comptabilite/operations/vente.html', context)


@login_required
def creer_depense(request):
    """Formulaire et traitement de dépense"""
    if request.method == 'POST':
        try:
            categorie_nom = request.POST.get('categorie', '')
            sous_categorie = request.POST.get('sous_categorie', '')

            # Résoudre la catégorie → compte comptable
            cat_config = next((c for c in CATEGORIES_DEPENSE if c['nom'] == categorie_nom), None)
            if cat_config:
                compte, _ = CompteModel.objects.get_or_create(
                    code=cat_config['code_compte'],
                    defaults={
                        'libelle': categorie_nom,
                        'type_compte': 'CHARGE',
                        'nature': 'CHARGE',
                        'actif': True,
                    }
                )
                compte_charge_id = compte.id
                libelle = f"{sous_categorie or categorie_nom}"
            else:
                compte_charge_id = request.POST.get('compte_charge_id') or None
                libelle = request.POST.get('description', 'Dépense')

            data = {
                'montant': Decimal(request.POST.get('montant', 0)),
                'mode_paiement': request.POST.get('mode_paiement', 'ESPECES'),
                'caisse_id': request.POST.get('caisse_id'),
                'notes': request.POST.get('notes', ''),
                'compte_charge_id': compte_charge_id,
                'beneficiaire': request.POST.get('beneficiaire', ''),
                'description': libelle,
                'date_operation': (
                    datetime.strptime(request.POST['date_operation'], '%Y-%m-%d').date()
                    if request.POST.get('date_operation') else date.today()
                ),
            }
            
            operation = DepenseOperation(request)
            result = operation.sauvegarder(data)
            
            messages.success(request, f"Dépense créée avec succès - Réf: {result.reference}")
            return redirect('comptabilite:operations')
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'caisses': Caisse.objects.filter(actif=True),
        'categories_depense': CATEGORIES_DEPENSE,
        'modes_paiement': Paiement.MODE_CHOICES,
        'title': 'Nouvelle dépense',
        'today': date.today(),
    }
    return render(request, 'comptabilite/operations/depense.html', context)


@login_required
def creer_recette(request):
    """Formulaire et traitement de recette"""
    if request.method == 'POST':
        try:
            data = {
                'montant': Decimal(request.POST.get('montant', 0)),
                'mode_paiement': request.POST.get('mode_paiement', 'ESPECES'),
                'caisse_id': request.POST.get('caisse_id'),
                'notes': request.POST.get('notes', ''),
            }
            
            operation = RecetteOperation(request)
            result = operation.sauvegarder(data)
            
            messages.success(request, f"Recette créée avec succès - Réf: {result.reference}")
            return redirect('comptabilite:operations')
            
        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'caisses': Caisse.objects.filter(actif=True),
        'modes_paiement': Paiement.MODE_CHOICES,
        'title': 'Nouvelle recette',
    }
    return render(request, 'comptabilite/operations/recette.html', context)


@login_required
def detail_operation(request, operation_id):
    """Détail d'une opération"""
    paiement = get_object_or_404(Paiement, id=operation_id)
    
    # Récupérer la facture associée si elle existe
    facture = None
    if paiement.objet and hasattr(paiement.objet, 'type_facture'):
        facture = paiement.objet
    
    context = {
        'operation': paiement,
        'facture': facture,
    }
    return render(request, 'comptabilite/operations/detail.html', context)


@login_required
def lettrer_operation(request, operation_id):
    """Lettrage d'une opération (validation supplémentaire)"""
    paiement = get_object_or_404(Paiement, id=operation_id)
    
    if paiement.statut == 'VALIDE':
        messages.warning(request, "Cette opération est déjà validée")
    else:
        paiement.statut = 'VALIDE'
        paiement.save()
        messages.success(request, f"Opération {paiement.reference} lettrée avec succès")
    
    return redirect('comptabilite:detail_operation', operation_id=operation_id)


@login_required
def creer_depot_client(request):
    """Dépôt client: le client approvisionne son compte en espèces"""
    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant', 0))
            client_id = request.POST.get('client_id')
            caisse_id = request.POST.get('caisse_id')
            mode = request.POST.get('mode_paiement', 'ESPECES')
            date_op = (
                datetime.strptime(request.POST['date_operation'], '%Y-%m-%d').date()
                if request.POST.get('date_operation') else date.today()
            )
            notes = request.POST.get('notes', '')

            if not caisse_id:
                raise ValueError("Veuillez sélectionner une caisse")

            client = get_object_or_404(Client, id=client_id)
            caisse = get_object_or_404(Caisse, id=caisse_id)
            tiers_client = _resolve_tiers_client(client)
            exercice = EcritureComptableService._get_exercice(date_op)

            # 1. Paiement
            paiement = Paiement.objects.create(
                reference=f"DEPOT-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                type_paiement='DEPOT',
                montant=montant,
                sens='ENTREE',
                mode=mode,
                caisse=caisse,
                client=client,
                statut='VALIDE',
                created_by=request.user,
                notes=notes,
            )

            # 2. Écriture comptable: 571 → 419
            EcritureComptableService.creer_ecriture_depot_client(
                caisse=caisse, montant=montant,
                libelle=f"Dépôt client {client.nom_complet}",
                tiers_client=tiers_client,
                user=request.user,
            )

            # 3. Mise à jour du solde client
            compte_client, _ = CompteClient.objects.select_for_update().get_or_create(
                client=client, exercice=exercice,
                defaults={'solde': montant}
            )
            if not compte_client.solde:
                compte_client.solde = Decimal('0')
            compte_client.solde += montant
            compte_client.save()

            paiement.est_comptabilise = True
            paiement.save()

            messages.success(request, f"Dépôt de {montant:,.0f} FCFA enregistré pour {client.nom_complet}")
            return redirect('comptabilite:operations')

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'clients': Client.objects.filter(statut='ACTIF').order_by('nom', 'prenom'),
        'caisses': Caisse.objects.filter(actif=True),
        'modes_paiement': Paiement.MODE_CHOICES,
        'today': date.today(),
        'title': 'Dépôt client',
        'client_soldes': _get_clients_soldes(),
    }
    return render(request, 'comptabilite/operations/depot_client.html', context)


@login_required
def creer_paiement_fournisseur(request):
    """Paiement fournisseur: règlement d'une dette fournisseur"""
    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant', 0))
            fournisseur_id = request.POST.get('fournisseur_id')
            caisse_id = request.POST.get('caisse_id')
            mode = request.POST.get('mode_paiement', 'ESPECES')
            date_op = (
                datetime.strptime(request.POST['date_operation'], '%Y-%m-%d').date()
                if request.POST.get('date_operation') else date.today()
            )
            reference = request.POST.get('reference_facture', '')
            notes = request.POST.get('notes', '')

            if not caisse_id:
                raise ValueError("Veuillez sélectionner une caisse")

            fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
            caisse = get_object_or_404(Caisse, id=caisse_id)
            tiers_fournisseur = _resolve_tiers_fournisseur(fournisseur)
            exercice = EcritureComptableService._get_exercice(date_op)
            libelle = f"Paiement {fournisseur.nom}"
            if reference:
                libelle += f" - {reference}"

            # 1. Paiement
            paiement = Paiement.objects.create(
                reference=f"PF-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                type_paiement='ACHAT',
                montant=montant,
                sens='SORTIE',
                mode=mode,
                caisse=caisse,
                statut='VALIDE',
                created_by=request.user,
                reference_externe=reference,
                notes=notes,
            )

            # 2. Écriture comptable: 401 → 571
            EcritureComptableService.creer_ecriture_paiement_fournisseur(
                caisse=caisse, montant=montant,
                libelle=libelle,
                tiers_fournisseur=tiers_fournisseur,
                user=request.user,
            )

            # 3. Mise à jour du solde fournisseur (diminution de la dette)
            compte_fournisseur, _ = CompteFournisseur.objects.select_for_update().get_or_create(
                fournisseur=fournisseur, exercice=exercice,
                defaults={'solde': -montant}
            )
            compte_fournisseur.solde -= montant
            compte_fournisseur.save()

            paiement.est_comptabilise = True
            paiement.save()

            messages.success(request, f"Paiement de {montant:,.0f} FCFA à {fournisseur.nom} enregistré")
            return redirect('comptabilite:operations')

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'fournisseurs': Fournisseur.objects.filter(actif=True).order_by('nom'),
        'caisses': Caisse.objects.filter(actif=True),
        'modes_paiement': Paiement.MODE_CHOICES,
        'today': date.today(),
        'title': 'Paiement fournisseur',
    }
    return render(request, 'comptabilite/operations/paiement_fournisseur.html', context)


@login_required
def creer_paiement_client(request):
    """Paiement de créance client: encaissement d'une dette client"""
    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant', 0))
            client_id = request.POST.get('client_id')
            caisse_id = request.POST.get('caisse_id')
            mode = request.POST.get('mode_paiement', 'ESPECES')
            date_op = (
                datetime.strptime(request.POST['date_operation'], '%Y-%m-%d').date()
                if request.POST.get('date_operation') else date.today()
            )
            notes = request.POST.get('notes', '')

            if not caisse_id:
                raise ValueError("Veuillez sélectionner une caisse")

            client = get_object_or_404(Client, id=client_id)
            caisse = get_object_or_404(Caisse, id=caisse_id)
            tiers_client = _resolve_tiers_client(client)
            exercice = EcritureComptableService._get_exercice(date_op)

            # 1. Paiement
            paiement = Paiement.objects.create(
                reference=f"ENC-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                type_paiement='REMBOURSEMENT',
                montant=montant,
                sens='ENTREE',
                mode=mode,
                caisse=caisse,
                client=client,
                statut='VALIDE',
                created_by=request.user,
                notes=notes,
            )

            # 2. Écriture comptable: 571 → 411
            EcritureComptableService.creer_ecriture_paiement_client(
                caisse=caisse, montant=montant,
                libelle=f"Encaissement créance {client.nom_complet}",
                tiers_client=tiers_client,
                user=request.user,
            )

            # 3. Mise à jour du solde client (la créance diminue)
            compte_client, _ = CompteClient.objects.select_for_update().get_or_create(
                client=client, exercice=exercice,
                defaults={'solde': montant}
            )
            if not compte_client.solde:
                compte_client.solde = Decimal('0')
            compte_client.solde += montant
            compte_client.save()

            paiement.est_comptabilise = True
            paiement.save()

            messages.success(request, f"Encaissement de {montant:,.0f} FCFA de {client.nom_complet} enregistré")
            return redirect('comptabilite:operations')

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'clients': Client.objects.filter(statut='ACTIF').order_by('nom', 'prenom'),
        'caisses': Caisse.objects.filter(actif=True),
        'modes_paiement': Paiement.MODE_CHOICES,
        'today': date.today(),
        'title': 'Paiement client',
        'client_soldes': _get_clients_soldes(),
    }
    return render(request, 'comptabilite/operations/paiement_client.html', context)


@login_required
def creer_remboursement_client(request):
    """Remboursement depot client: le client retire de l'argent de son compte"""
    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant', 0))
            client_id = request.POST.get('client_id')
            caisse_id = request.POST.get('caisse_id')
            mode = request.POST.get('mode_paiement', 'ESPECES')
            date_op = (
                datetime.strptime(request.POST['date_operation'], '%Y-%m-%d').date()
                if request.POST.get('date_operation') else date.today()
            )
            notes = request.POST.get('notes', '')

            if not caisse_id:
                raise ValueError("Veuillez sélectionner une caisse")

            client = get_object_or_404(Client, id=client_id)
            caisse = get_object_or_404(Caisse, id=caisse_id)
            tiers_client = _resolve_tiers_client(client)
            exercice = EcritureComptableService._get_exercice(date_op)

            # Verifier solde suffisant
            compte_client = CompteClient.objects.select_for_update().filter(client=client, exercice=exercice).first()
            solde_disponible = compte_client.solde if compte_client else Decimal('0')
            if solde_disponible < montant:
                raise ValueError(
                    f"Solde insuffisant: {solde_disponible:,.0f} FCFA disponible, "
                    f"{montant:,.0f} FCFA demande"
                )

            # 1. Paiement
            paiement = Paiement.objects.create(
                reference=f"REM-{datetime.now().strftime('%Y%m%d%H%M%S%f')}",
                type_paiement='REMBOURSEMENT',
                montant=montant,
                sens='SORTIE',
                mode=mode,
                caisse=caisse,
                client=client,
                statut='VALIDE',
                created_by=request.user,
                notes=notes,
            )

            # 2. Ecriture comptable: 419 → 571
            EcritureComptableService.creer_ecriture_remboursement_client(
                caisse=caisse, montant=montant,
                libelle=f"Remboursement depot {client.nom_complet}",
                tiers_client=tiers_client,
                user=request.user,
            )

            # 3. Mise a jour du solde client (diminution)
            compte_client.solde -= montant
            compte_client.save()

            paiement.est_comptabilise = True
            paiement.save()

            messages.success(request, f"Remboursement de {montant:,.0f} FCFA a {client.nom_complet}")
            return redirect('comptabilite:operations')

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'clients': Client.objects.filter(statut='ACTIF').order_by('nom', 'prenom'),
        'caisses': Caisse.objects.filter(actif=True),
        'modes_paiement': Paiement.MODE_CHOICES,
        'today': date.today(),
        'title': 'Remboursement client',
        'client_soldes': _get_clients_soldes(),
    }
    return render(request, 'comptabilite/operations/remboursement_client.html', context)


@login_required
def creer_depot_banque(request):
    """Depot banque: versement d'especes de la caisse vers le compte bancaire"""
    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant', 0))
            caisse_id = request.POST.get('caisse_id')
            date_op = (
                datetime.strptime(request.POST['date_operation'], '%Y-%m-%d').date()
                if request.POST.get('date_operation') else date.today()
            )
            notes = request.POST.get('notes', '')
            reference = request.POST.get('reference', '')

            caisse = get_object_or_404(Caisse, id=caisse_id)

            # 1. Ecriture comptable: 521 → 571
            EcritureComptableService.creer_ecriture_depot_banque(
                caisse=caisse, montant=montant,
                libelle=f"Depot banque depuis {caisse.nom}",
                user=request.user,
            )

            messages.success(request, f"Depot banque de {montant:,.0f} FCFA depuis {caisse.nom}")
            return redirect('comptabilite:operations')

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'caisses': Caisse.objects.filter(actif=True),
        'today': date.today(),
        'title': 'Depot banque',
    }
    return render(request, 'comptabilite/operations/depot_banque.html', context)


@login_required
def creer_retrait_banque(request):
    """Retrait banque: retrait d'argent du compte bancaire vers la caisse"""
    if request.method == 'POST':
        try:
            montant = Decimal(request.POST.get('montant', 0))
            caisse_id = request.POST.get('caisse_id')
            date_op = (
                datetime.strptime(request.POST['date_operation'], '%Y-%m-%d').date()
                if request.POST.get('date_operation') else date.today()
            )
            notes = request.POST.get('notes', '')
            reference = request.POST.get('reference', '')

            caisse = get_object_or_404(Caisse, id=caisse_id)

            # 1. Ecriture comptable: 571 → 521
            EcritureComptableService.creer_ecriture_retrait_banque(
                caisse=caisse, montant=montant,
                libelle=f"Retrait banque vers {caisse.nom}",
                user=request.user,
            )

            messages.success(request, f"Retrait banque de {montant:,.0f} FCFA vers {caisse.nom}")
            return redirect('comptabilite:operations')

        except Exception as e:
            messages.error(request, f"Erreur: {str(e)}")
            return redirect('comptabilite:operations')

    context = {
        'caisses': Caisse.objects.filter(actif=True),
        'today': date.today(),
        'title': 'Retrait banque',
    }
    return render(request, 'comptabilite/operations/retrait_banque.html', context)


@csrf_exempt
@require_http_methods(["POST"])
@login_required
def api_calcul_tva(request):
    """API de calcul automatique de la TVA"""
    try:
        data = json.loads(request.body)
        montant_ht = Decimal(str(data.get('montant_ht', 0)))
        taux_tva = Decimal(str(data.get('taux_tva', 0)))
        
        montant_tva = (montant_ht * taux_tva) / Decimal('100')
        montant_ttc = montant_ht + montant_tva
        
        return JsonResponse({
            'success': True,
            'montant_ht': float(montant_ht),
            'montant_tva': float(montant_tva),
            'montant_ttc': float(montant_ttc),
            'taux_tva': float(taux_tva)
        })
        
    except (json.JSONDecodeError, InvalidOperation, KeyError) as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
        
        
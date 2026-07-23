# apps/comptabilite/views/parametres.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from datetime import date
from decimal import Decimal
import json

from ..models import (
    ExerciceModel, EcritureModel, LigneEcritureModel, 
    JournalModel, CompteModel, ConfigurationEntreprise,
    SoldesInitiaux, ParametreEntreprise
)
from ..services.initialisation import InitialisationComptable
from ..services.initialisation_auto import InitialisationAutoService


@login_required
def exercices_liste(request):
    """Liste des exercices comptables"""
    exercices = ExerciceModel.objects.all().order_by('-date_debut')
    
    # Déterminer l'exercice courant
    today = date.today()
    exercice_courant = None
    for ex in exercices:
        if ex.date_debut <= today <= ex.date_fin and not ex.cloture:
            exercice_courant = ex
            break
    
    context = {
        'exercices': exercices,
        'exercice_courant': exercice_courant,
        'titre': 'Exercices comptables',
        'header': 'Exercices comptables',
        'subtitle': 'Gestion des exercices et clôtures'
    }
    return render(request, 'comptabilite/parametres/exercices.html', context)


@login_required
def cloturer_exercice(request, exercice_id):
    """Clôturer un exercice comptable"""
    exercice = get_object_or_404(ExerciceModel, id=exercice_id)
    
    if request.method == 'POST':
        if exercice.cloture:
            messages.warning(request, f"L'exercice {exercice.code} est déjà clôturé")
        else:
            exercice.cloture = True
            exercice.date_cloture = date.today()
            exercice.save()
            messages.success(request, f"✓ Exercice {exercice.code} clôturé avec succès")
        
        return redirect('comptabilite:exercices_liste')
    
    context = {
        'exercice': exercice,
        'titre': f'Clôturer exercice {exercice.code}'
    }
    return render(request, 'comptabilite/parametres/cloturer.html', context)


@login_required
def rouvrir_exercice(request, exercice_id):
    """Rouvrir un exercice comptable clôturé"""
    exercice = get_object_or_404(ExerciceModel, id=exercice_id)
    
    if request.method == 'POST':
        if not exercice.cloture:
            messages.warning(request, f"L'exercice {exercice.code} n'est pas clôturé")
        else:
            exercice.cloture = False
            exercice.date_cloture = None
            exercice.save()
            messages.success(request, f"✓ Exercice {exercice.code} rouvert avec succès")
        
        return redirect('comptabilite:exercices_liste')
    
    context = {
        'exercice': exercice,
        'titre': f'Rouvrir exercice {exercice.code}'
    }
    return render(request, 'comptabilite/parametres/rouvrir.html', context)


@login_required
def initialisation_soldes(request):
    """Formulaire des soldes initiaux (écriture d'ouverture)"""
    
    # Vérifier si déjà initialisé
    config = ConfigurationEntreprise.objects.first()
    
    if config and config.est_initialise:
        messages.warning(request, "Le système est déjà initialisé")
        return redirect('comptabilite:dashboard')
    
    # Récupérer l'exercice courant
    exercice_courant = ExerciceModel.objects.filter(cloture=False, date_debut__lte=date.today(), date_fin__gte=date.today()).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    # Récupérer les soldes existants (pour modification)
    soldes_existants = None
    if config:
        soldes_existants = SoldesInitiaux.objects.filter(configuration=config).first()
    
    context = {
        'exercice_courant': exercice_courant,
        'soldes': soldes_existants,
        'titre': 'Soldes initiaux',
        'header': 'Initialisation comptable',
        'subtitle': 'Saisie des soldes d\'ouverture'
    }
    return render(request, 'comptabilite/parametres/soldes_initiaux.html', context)


@login_required
def verifier_initialisation(request):
    """Vérifier si l'initialisation est déjà faite (AJAX)"""
    config = ConfigurationEntreprise.objects.first()
    est_initialise = config and config.est_initialise
    
    return JsonResponse({'initialise': est_initialise})


@login_required
@transaction.atomic
def enregistrer_initialisation(request):
    """Enregistrer les soldes initiaux et créer l'écriture d'ouverture"""
    
    if request.method != 'POST':
        return redirect('comptabilite:initialisation_soldes')
    
    try:
        # Récupérer les données du formulaire
        caisse = Decimal(request.POST.get('caisse', 0))
        banque = Decimal(request.POST.get('banque', 0))
        stocks = Decimal(request.POST.get('stocks', 0))
        clients = Decimal(request.POST.get('clients', 0))
        fournisseurs = Decimal(request.POST.get('fournisseurs', 0))
        capital_social = Decimal(request.POST.get('capital_social', 0))
        nom_entreprise = request.POST.get('nom_entreprise', 'Mon Entreprise')
        
        # Calcul du capital réel (Actif - Dettes)
        actif = caisse + banque + stocks + clients
        dettes = fournisseurs
        capital_reel = actif - dettes
        
        # Récupérer l'exercice courant
        exercice = ExerciceModel.objects.filter(cloture=False).first()
        if not exercice:
            annee = date.today().year
            exercice = ExerciceModel.objects.create(
                code=str(annee),
                date_debut=date(annee, 1, 1),
                date_fin=date(annee, 12, 31),
                cloture=False
            )
        
        # Récupérer le journal OD
        journal, _ = JournalModel.objects.get_or_create(
            code='OD',
            defaults={'libelle': 'Opérations Diverses', 'type_journal': 'OD', 'actif': True}
        )
        
        # Créer l'écriture d'ouverture
        reference = f"OUV-{exercice.code}"
        ecriture = EcritureModel.objects.create(
            reference=reference,
            date_ecriture=date.today(),
            libelle=f"Écriture d'ouverture - Exercice {exercice.code}",
            journal=journal,
            piece="INIT-001",
            exercice=exercice,
            validee=True,
            date_validation=date.today(),
            created_by=request.user.username
        )
        
        # Récupérer les comptes
        compte_caisse = CompteModel.objects.filter(code='571').first()
        compte_banque = CompteModel.objects.filter(code='521').first()
        compte_stocks = CompteModel.objects.filter(code='31').first()
        compte_clients = CompteModel.objects.filter(code='411').first()
        compte_fournisseurs = CompteModel.objects.filter(code='401').first()
        compte_capital = CompteModel.objects.filter(code='101').first()
        
        # Lignes d'écriture (Débit)
        if caisse > 0 and compte_caisse:
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_caisse,
                debit=caisse,
                credit=0,
                libelle="Solde initial caisse"
            )
        
        if banque > 0 and compte_banque:
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_banque,
                debit=banque,
                credit=0,
                libelle="Solde initial banque"
            )
        
        if stocks > 0 and compte_stocks:
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_stocks,
                debit=stocks,
                credit=0,
                libelle="Stock initial"
            )
        
        if clients > 0 and compte_clients:
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_clients,
                debit=clients,
                credit=0,
                libelle="Créances clients initiales"
            )
        
        # Lignes d'écriture (Crédit)
        if fournisseurs > 0 and compte_fournisseurs:
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_fournisseurs,
                debit=0,
                credit=fournisseurs,
                libelle="Dettes fournisseurs initiales"
            )
        
        if capital_reel != 0 and compte_capital:
            if capital_reel > 0:
                LigneEcritureModel.objects.create(
                    ecriture=ecriture,
                    compte=compte_capital,
                    debit=0,
                    credit=capital_reel,
                    libelle="Capital social d'ouverture"
                )
            else:
                compte_perte = CompteModel.objects.filter(code='131').first()
                if compte_perte:
                    LigneEcritureModel.objects.create(
                        ecriture=ecriture,
                        compte=compte_perte,
                        debit=abs(capital_reel),
                        credit=0,
                        libelle="Report à nouveau débiteur"
                    )
        
        # Sauvegarder la configuration
        config, created = ConfigurationEntreprise.objects.get_or_create(
            defaults={
                'nom': nom_entreprise,
                'exercice_annee': exercice.code,
                'est_initialise': True,
                'date_initialisation': date.today(),
                'nombre_comptes': CompteModel.objects.count(),
                'exercice_id': exercice.id
            }
        )
        
        if not created:
            config.est_initialise = True
            config.date_initialisation = date.today()
            config.save()
        
        # Sauvegarder les soldes
        SoldesInitiaux.objects.update_or_create(
            configuration=config,
            defaults={
                'capital_social': capital_social,
                'capital_reel': capital_reel,
                'caisse': caisse,
                'banque': banque,
                'clients': clients,
                'fournisseurs': fournisseurs,
                'stocks': stocks
            }
        )
        
        # Créer les paramètres par défaut
        ParametreEntreprise.objects.get_or_create(
            entreprise=config,
            defaults={
                'mode_paie': 'SIMPLE',
                'gerer_cnps': False,
                'gerer_impots': False,
                'gerer_avances': True
            }
        )
        
        messages.success(request, f'✓ Initialisation comptable réussie ! Écriture {reference} créée.')
        return redirect('comptabilite:dashboard')
        
    except Exception as e:
        messages.error(request, f'Erreur lors de l\'initialisation: {str(e)}')
        return redirect('comptabilite:initialisation_soldes')


# ========== INITIALISATION DU PLAN COMPTABLE ==========

@login_required
def initialisation_plan_comptable(request):
    """Page d'initialisation du plan comptable SYSCOHADA"""
    
    service = InitialisationComptable()
    stats = service.get_stats()
    
    context = {
        'stats': stats,
        'total_comptes_attendu': 847,
        'statut': 'initialisé' if stats['total'] > 0 else 'non initialisé',
        'titre': 'Plan comptable SYSCOHADA',
        'header': 'Initialisation comptable',
        'subtitle': 'Chargement du plan comptable SYSCOHADA'
    }
    return render(request, 'comptabilite/initialisation/plan_comptable.html', context)


@csrf_exempt
@login_required
def api_initialiser_plan_comptable(request):
    """API pour initialiser le plan comptable SYSCOHADA"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            force = data.get('force', False)
            
            service = InitialisationComptable()
            
            # Vérifier si des comptes existent
            if CompteModel.objects.exists() and not force:
                return JsonResponse({
                    'success': False,
                    'error': f"Des comptes existent déjà ({CompteModel.objects.count()} comptes). Utilisez force=True pour réinitialiser."
                })
            
            # Importer les comptes
            service.importer_comptes(force=force)
            stats = service.get_stats()
            
            return JsonResponse({
                'success': True,
                'message': 'Plan comptable SYSCOHADA importé avec succès',
                'stats': stats
            })
        except FileNotFoundError as e:
            return JsonResponse({
                'success': False,
                'error': f"Fichier plan comptable non trouvé: {str(e)}"
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({'success': False, 'error': 'Méthode non autorisée'}, status=405)


@login_required
def api_stats_plan_comptable(request):
    """API pour obtenir les statistiques du plan comptable"""
    service = InitialisationComptable()
    stats = service.get_stats()
    return JsonResponse({'success': True, 'stats': stats})


# ========== ASSISTANT DE MISE EN SERVICE ==========

@login_required
def assistant_situation_initiale(request):
    """Assistant de mise en service — construction situation initiale"""
    service = InitialisationAutoService()
    config = service.get_config()
    context = {
        'deja_validee': config.situation_initiale_validee,
        'contrepartie_courante': config.contrepartie_situation,
        'titre': 'Situation initiale',
        'header': 'Assistant de mise en service',
        'subtitle': 'Construction de la situation initiale du logiciel',
    }
    return render(request, 'comptabilite/parametres/initialisation_auto.html', context)


@login_required
def api_etat_avancement(request):
    """GET → JSON complet de l'état d'avancement"""
    service = InitialisationAutoService()
    data = service.get_etat_avancement()

    # Ajouter l'écriture existante si déjà validée
    if data['deja_validee']:
        ecriture = service.get_ecriture_existante()
        if ecriture:
            data['ecriture'] = {
                'id': ecriture.id,
                'reference': ecriture.reference,
                'date_ecriture': ecriture.date_ecriture,
            }

    # Ajouter l'aperçu si demandé
    contrepartie = request.GET.get('contrepartie')
    if contrepartie:
        apercu = service.get_apercu_ecriture(contrepartie)
        data['apercu'] = apercu

    return JsonResponse(data)


@login_required
@csrf_exempt
def api_valider_situation(request):
    """POST {contrepartie} → valide + génère écriture"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'POST required'})

    try:
        data = json.loads(request.body)
        service = InitialisationAutoService()
        result = service.valider_situation(
            contrepartie_code=data.get('contrepartie', '101'),
            user=request.user
        )
        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
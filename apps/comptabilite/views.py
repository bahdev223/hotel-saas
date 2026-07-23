# apps/comptabilite_dashboard/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import date, datetime

from apps.comptabilite.models import (
    ExerciceModel, CompteModel, EcritureModel, 
    LigneEcritureModel, JournalModel, TiersModel
)


@login_required
def dashboard(request):
    """Dashboard comptable principal"""
    
    # Récupérer l'exercice en cours
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    # Statistiques
    total_ecritures = EcritureModel.objects.filter(exercice=exercice_courant).count()
    total_ecritures_validees = EcritureModel.objects.filter(exercice=exercice_courant, validee=True).count()
    
    # Soldes des comptes de trésorerie
    try:
        compte_caisse = CompteModel.objects.get(code="571")
        compte_banque = CompteModel.objects.get(code="521")
        
        solde_caisse = LigneEcritureModel.objects.filter(
            ecriture__exercice=exercice_courant,
            compte=compte_caisse
        ).aggregate(
            total=Sum('debit') - Sum('credit')
        )['total'] or 0
        
        solde_banque = LigneEcritureModel.objects.filter(
            ecriture__exercice=exercice_courant,
            compte=compte_banque
        ).aggregate(
            total=Sum('debit') - Sum('credit')
        )['total'] or 0
    except:
        solde_caisse = 0
        solde_banque = 0
    
    # Dernières écritures
    dernieres_ecritures = EcritureModel.objects.filter(
        exercice=exercice_courant
    ).order_by('-date_ecriture')[:10]
    
    context = {
        'exercice_courant': exercice_courant,
        'total_ecritures': total_ecritures,
        'total_ecritures_validees': total_ecritures_validees,
        'solde_caisse': solde_caisse,
        'solde_banque': solde_banque,
        'dernieres_ecritures': dernieres_ecritures,
        'date_aujourdhui': date.today(),
        'titre': 'Tableau de bord comptable'
    }
    
    return render(request, 'comptabilite/dashboard.html', context)


@login_required
def ecritures_liste(request):
    """Liste des écritures comptables"""
    
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    # Filtres
    statut = request.GET.get('statut')
    journal = request.GET.get('journal')
    
    ecritures = EcritureModel.objects.filter(exercice=exercice_courant)
    
    if statut == 'validee':
        ecritures = ecritures.filter(validee=True)
    elif statut == 'non_validee':
        ecritures = ecritures.filter(validee=False)
    
    if journal:
        ecritures = ecritures.filter(journal__code=journal)
    
    ecritures = ecritures.order_by('-date_ecriture', '-created_at')
    
    journaux = JournalModel.objects.filter(actif=True)
    
    context = {
        'ecritures': ecritures,
        'journaux': journaux,
        'exercice_courant': exercice_courant,
        'filtre_statut': statut,
        'filtre_journal': journal,
        'titre': 'Écritures comptables'
    }
    
    return render(request, 'comptabilite/ecritures/liste.html', context)


@login_required
def ecriture_detail(request, ecriture_id):
    """Détail d'une écriture"""
    
    ecriture = get_object_or_404(EcritureModel, id=ecriture_id)
    lignes = ecriture.lignes.all()
    
    # Vérifier équilibre
    total_debit = sum(l.debit for l in lignes)
    total_credit = sum(l.credit for l in lignes)
    est_equilibree = total_debit == total_credit
    
    context = {
        'ecriture': ecriture,
        'lignes': lignes,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'est_equilibree': est_equilibree,
        'titre': f'Écriture {ecriture.reference}'
    }
    
    return render(request, 'comptabilite/ecritures/detail.html', context)


@login_required
def ecriture_valider(request, ecriture_id):
    """Valider une écriture"""
    
    ecriture = get_object_or_404(EcritureModel, id=ecriture_id)
    
    if request.method == 'POST':
        ecriture.validee = True
        ecriture.date_validation = timezone.now()
        ecriture.save()
        messages.success(request, f'Écriture {ecriture.reference} validée avec succès')
    
    return redirect('comptabilite:ecriture_detail', ecriture_id=ecriture_id)


@login_required
def comptes_liste(request):
    """Liste des comptes comptables"""
    
    # Récupérer tous les comptes
    comptes = CompteModel.objects.filter(actif=True).order_by('code')
    
    # Regrouper par classe
    classes = {}
    for i in range(1, 10):
        classe_comptes = comptes.filter(code__startswith=str(i))
        if classe_comptes.exists():
            classes[str(i)] = {
                'libelle': _get_classe_libelle(str(i)),
                'comptes': classe_comptes
            }
    
    context = {
        'classes': classes,
        'titre': 'Plan comptable SYSCOHADA'
    }
    
    return render(request, 'comptabilite/comptes/liste.html', context)


@login_required
def bilan(request):
    """Générer le bilan comptable"""
    
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    date_bilan = request.GET.get('date', date.today().isoformat())
    
    # Récupérer les soldes des comptes de bilan
    comptes_actif = CompteModel.objects.filter(categorie='bilan', nature='ACTIF')
    comptes_passif = CompteModel.objects.filter(categorie='bilan', nature='PASSIF')
    
    actif = []
    passif = []
    
    for compte in comptes_actif:
        solde = _calculer_solde_compte(compte, exercice_courant)
        if solde != 0:
            actif.append({'compte': compte, 'solde': solde})
    
    for compte in comptes_passif:
        solde = _calculer_solde_compte(compte, exercice_courant)
        if solde != 0:
            passif.append({'compte': compte, 'solde': solde})
    
    total_actif = sum(a['solde'] for a in actif)
    total_passif = sum(p['solde'] for p in passif)
    
    context = {
        'exercice_courant': exercice_courant,
        'date_bilan': date_bilan,
        'actif': actif,
        'passif': passif,
        'total_actif': total_actif,
        'total_passif': total_passif,
        'difference': total_actif - total_passif,
        'titre': 'Bilan comptable'
    }
    
    return render(request, 'comptabilite/bilan.html', context)


@login_required
def compte_resultat(request):
    """Générer le compte de résultat"""
    
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    # Récupérer les comptes de résultat
    comptes_charges = CompteModel.objects.filter(categorie='resultat', nature='CHARGE')
    comptes_produits = CompteModel.objects.filter(categorie='resultat', nature='PRODUIT')
    
    charges = []
    produits = []
    
    for compte in comptes_charges:
        solde = _calculer_solde_compte(compte, exercice_courant)
        if solde != 0:
            charges.append({'compte': compte, 'solde': solde})
    
    for compte in comptes_produits:
        solde = _calculer_solde_compte(compte, exercice_courant)
        if solde != 0:
            produits.append({'compte': compte, 'solde': solde})
    
    total_charges = sum(c['solde'] for c in charges)
    total_produits = sum(p['solde'] for p in produits)
    resultat = total_produits - total_charges
    
    context = {
        'exercice_courant': exercice_courant,
        'charges': charges,
        'produits': produits,
        'total_charges': total_charges,
        'total_produits': total_produits,
        'resultat': resultat,
        'resultat_texte': 'Bénéfice' if resultat > 0 else 'Perte' if resultat < 0 else 'Équilibre',
        'titre': 'Compte de résultat'
    }
    
    return render(request, 'comptabilite/compte_resultat.html', context)


@login_required
def balance(request):
    """Générer la balance des comptes"""
    
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    date_debut = request.GET.get('date_debut', exercice_courant.date_debut.isoformat())
    date_fin = request.GET.get('date_fin', date.today().isoformat())
    
    # Récupérer tous les comptes avec mouvements
    comptes_avec_mouvements = CompteModel.objects.filter(
        lignes__ecriture__exercice=exercice_courant
    ).distinct().order_by('code')
    
    balance_data = []
    for compte in comptes_avec_mouvements:
        lignes = LigneEcritureModel.objects.filter(
            compte=compte,
            ecriture__exercice=exercice_courant
        )
        
        total_debit = sum(l.debit for l in lignes)
        total_credit = sum(l.credit for l in lignes)
        solde = total_debit - total_credit if compte.nature in ['ACTIF', 'CHARGE'] else total_credit - total_debit
        
        balance_data.append({
            'compte': compte,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'solde': solde
        })
    
    total_general_debit = sum(b['total_debit'] for b in balance_data)
    total_general_credit = sum(b['total_credit'] for b in balance_data)
    
    context = {
        'exercice_courant': exercice_courant,
        'balance_data': balance_data,
        'total_general_debit': total_general_debit,
        'total_general_credit': total_general_credit,
        'date_debut': date_debut,
        'date_fin': date_fin,
        'titre': 'Balance des comptes'
    }
    
    return render(request, 'comptabilite/balance.html', context)


# Fonctions utilitaires
def _get_classe_libelle(classe):
    """Retourne le libellé de la classe"""
    libelles = {
        '1': 'RESSOURCES DURABLES (Capital)',
        '2': 'ACTIFS IMMOBILISÉS',
        '3': 'STOCKS',
        '4': 'TIERS',
        '5': 'TRÉSORERIE',
        '6': 'CHARGES',
        '7': 'PRODUITS',
        '8': 'RÉSULTATS',
        '9': 'HORS BILAN'
    }
    return libelles.get(classe, f'Classe {classe}')


def _calculer_solde_compte(compte, exercice):
    """Calcule le solde d'un compte"""
    lignes = LigneEcritureModel.objects.filter(
        compte=compte,
        ecriture__exercice=exercice
    )
    
    total_debit = sum(l.debit for l in lignes)
    total_credit = sum(l.credit for l in lignes)
    
    if compte.nature in ['ACTIF', 'CHARGE']:
        return total_debit - total_credit
    else:
        return total_credit - total_debit
    
    
    
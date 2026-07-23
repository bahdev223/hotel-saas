# apps/comptabilite/views/ecritures.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from django.utils import timezone
from datetime import date, datetime
from decimal import Decimal

from ..models import (
    ExerciceModel, CompteModel, EcritureModel, 
    LigneEcritureModel, JournalModel
)


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
    
    # 🔥 CRÉER UNE NOUVELLE LISTE AVEC LES TOTAUX CALCULÉS (pas d'assignation directe)
    ecritures_with_totals = []
    total_general_debit = Decimal('0')
    total_general_credit = Decimal('0')
    
    for ecriture in ecritures:
        lignes = ecriture.lignes.all()
        total_debit = sum(l.debit for l in lignes)
        total_credit = sum(l.credit for l in lignes)
        total_general_debit += total_debit
        total_general_credit += total_credit
        
        # Créer un dictionnaire avec les données de l'écriture + totaux
        ecritures_with_totals.append({
            'id': ecriture.id,
            'reference': ecriture.reference,
            'date_ecriture': ecriture.date_ecriture,
            'journal': ecriture.journal,
            'libelle': ecriture.libelle,
            'validee': ecriture.validee,
            'total_debit': total_debit,
            'total_credit': total_credit,
            'piece': ecriture.piece,
            'created_by': ecriture.created_by,
        })
    
    journaux = JournalModel.objects.filter(actif=True)
    
    # Pour les selects dans le modal
    comptes_actifs = CompteModel.objects.filter(actif=True, est_mouvement=True).order_by('code')
    
    context = {
        'ecritures': ecritures_with_totals,  # ← Utiliser la nouvelle liste
        'journaux': journaux,
        'comptes_actifs': comptes_actifs,
        'exercice_courant': exercice_courant,
        'total_debit': total_general_debit,
        'total_credit': total_general_credit,
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
    
    # Calculer les totaux
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



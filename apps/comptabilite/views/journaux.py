# apps/comptabilite/views/journaux.py
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from ..models import JournalModel, EcritureModel, LigneEcritureModel


@login_required
def journaux_liste(request):
    """Liste des journaux comptables"""
    journaux = JournalModel.objects.filter(actif=True).order_by('code')
    
    # Statistiques par journal
    for journal in journaux:
        journal.nb_ecritures = EcritureModel.objects.filter(journal=journal).count()
        lignes = LigneEcritureModel.objects.filter(ecriture__journal=journal)
        journal.total_debit = lignes.aggregate(total=Sum('debit'))['total'] or 0
        journal.total_credit = lignes.aggregate(total=Sum('credit'))['total'] or 0
    
    context = {
        'journaux': journaux,
        'titre': 'Journaux comptables',
        'header': 'Journaux comptables',
        'subtitle': 'Gestion des journaux (ACHATS, VENTES, CAISSE, BANQUE, OD)'
    }
    return render(request, 'comptabilite/journaux/liste.html', context)


@login_required
def journal_detail(request, journal_id):
    """Détail d'un journal avec ses écritures"""
    journal = get_object_or_404(JournalModel, id=journal_id)
    ecritures = EcritureModel.objects.filter(journal=journal).order_by('-date_ecriture')
    
    total_debit = LigneEcritureModel.objects.filter(
        ecriture__journal=journal
    ).aggregate(total=Sum('debit'))['total'] or 0
    total_credit = LigneEcritureModel.objects.filter(
        ecriture__journal=journal
    ).aggregate(total=Sum('credit'))['total'] or 0
    
    context = {
        'journal': journal,
        'ecritures': ecritures,
        'total_debit': total_debit,
        'total_credit': total_credit,
        'titre': f'Journal {journal.code} - {journal.libelle}',
        'header': f'Journal {journal.code}',
        'subtitle': journal.libelle
    }
    return render(request, 'comptabilite/journaux/detail.html', context)


@login_required
def achats_liste(request):
    """Journal des achats (code: AC)"""
    journal = get_object_or_404(JournalModel, code='ACHATS')
    ecritures = EcritureModel.objects.filter(journal=journal).order_by('-date_ecriture')
    
    context = {
        'journal': journal,
        'ecritures': ecritures,
        'titre': 'Journal des achats',
        'header': 'Journal des achats',
        'subtitle': 'Toutes les écritures d\'achats'
    }
    return render(request, 'comptabilite/journaux/achats.html', context)


@login_required
def achat_detail(request, achat_id):
    """Détail d'un achat"""
    ecriture = get_object_or_404(EcritureModel, id=achat_id)
    lignes = ecriture.lignes.all()
    
    context = {
        'ecriture': ecriture,
        'lignes': lignes,
        'titre': f'Achat {ecriture.reference}',
        'header': f'Achat {ecriture.reference}',
        'subtitle': ecriture.libelle
    }
    return render(request, 'comptabilite/journaux/achat_detail.html', context)


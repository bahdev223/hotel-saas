# apps/comptabilite/views/exports.py
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum
from decimal import Decimal
from ..models import ExerciceModel, EcritureModel, LigneEcritureModel, CompteModel
from ..services.export_service import ExportComptableService


@login_required
def export_balance_pdf(request):
    """Export balance en PDF"""
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    lignes = LigneEcritureModel.objects.filter(
        ecriture__exercice=exercice_courant
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    ).order_by('compte__code')
    
    balance_data = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    
    for ligne in lignes:
        debit = ligne['total_debit'] or Decimal('0')
        credit = ligne['total_credit'] or Decimal('0')
        total_debit += debit
        total_credit += credit
        balance_data.append({
            'compte__code': ligne['compte__code'],
            'compte__libelle': ligne['compte__libelle'],
            'total_debit': debit,
            'total_credit': credit,
            'solde': debit - credit
        })
    
    return ExportComptableService.export_balance_pdf(balance_data, total_debit, total_credit, exercice_courant)


@login_required
def export_balance_excel(request):
    """Export balance en Excel"""
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    lignes = LigneEcritureModel.objects.filter(
        ecriture__exercice=exercice_courant
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    ).order_by('compte__code')
    
    balance_data = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    
    for ligne in lignes:
        debit = ligne['total_debit'] or Decimal('0')
        credit = ligne['total_credit'] or Decimal('0')
        total_debit += debit
        total_credit += credit
        balance_data.append({
            'compte__code': ligne['compte__code'],
            'compte__libelle': ligne['compte__libelle'],
            'total_debit': debit,
            'total_credit': credit,
            'solde': debit - credit
        })
    
    return ExportComptableService.export_balance_excel(balance_data, total_debit, total_credit, exercice_courant)


@login_required
def export_bilan_pdf(request):
    """Export bilan en PDF"""
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    # Actif (comptes 2)
    actif = LigneEcritureModel.objects.filter(
        compte__code__startswith='2',
        ecriture__exercice=exercice_courant
    ).aggregate(total=Sum('debit'))['total'] or 0
    
    # Passif (comptes 4)
    passif = LigneEcritureModel.objects.filter(
        compte__code__startswith='4',
        ecriture__exercice=exercice_courant
    ).aggregate(total=Sum('credit'))['total'] or 0
    
    return ExportComptableService.export_bilan_pdf(actif, passif, exercice_courant)


@login_required
def export_resultat_pdf(request):
    """Export compte de résultat en PDF"""
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    produits = LigneEcritureModel.objects.filter(
        compte__code__startswith='7',
        ecriture__exercice=exercice_courant
    ).aggregate(total=Sum('credit'))['total'] or 0
    
    charges = LigneEcritureModel.objects.filter(
        compte__code__startswith='6',
        ecriture__exercice=exercice_courant
    ).aggregate(total=Sum('debit'))['total'] or 0
    
    return ExportComptableService.export_resultat_pdf(produits, charges, exercice_courant)


@login_required
def export_ecritures_csv(request):
    """Export écritures en CSV"""
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    ecritures = EcritureModel.objects.filter(exercice=exercice_courant).order_by('-date_ecriture')
    
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    
    for ecriture in ecritures:
        lignes = ecriture.lignes.all()
        ecriture.total_debit = sum(l.debit for l in lignes)
        ecriture.total_credit = sum(l.credit for l in lignes)
        total_debit += ecriture.total_debit
        total_credit += ecriture.total_credit
    
    return ExportComptableService.export_ecritures_csv(ecritures, total_debit, total_credit)


@login_required
def export_ecritures_excel(request):
    """Export écritures en Excel"""
    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()
    
    ecritures = EcritureModel.objects.filter(exercice=exercice_courant).order_by('-date_ecriture')
    
    total_debit = Decimal('0')
    total_credit = Decimal('0')
    
    for ecriture in ecritures:
        lignes = ecriture.lignes.all()
        ecriture.total_debit = sum(l.debit for l in lignes)
        ecriture.total_credit = sum(l.credit for l in lignes)
        total_debit += ecriture.total_debit
        total_credit += ecriture.total_credit
    
    return ExportComptableService.export_ecritures_excel(ecritures, total_debit, total_credit, exercice_courant)


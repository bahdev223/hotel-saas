# apps/comptabilite/views/bilan.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, DecimalField, ExpressionWrapper
from datetime import date
from decimal import Decimal

from apps.comptabilite.models import ExerciceModel
from ..models import LigneEcritureModel, CompteModel


@login_required
def bilan(request):
    """Bilan comptable (actif / passif)"""

    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()

    # ACTIF : nature='ACTIF' + categorie='bilan'
    # solde = SUM(debit) - SUM(credit)
    details_actif = LigneEcritureModel.objects.filter(
        compte__nature='ACTIF',
        compte__categorie='bilan',
        ecriture__exercice=exercice_courant
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
    ).annotate(
        solde=ExpressionWrapper(
            F('total_debit') - F('total_credit'),
            output_field=DecimalField()
        )
    ).filter(solde__gt=0).order_by('compte__code')

    # PASSIF : nature='PASSIF' + categorie='bilan'
    # solde = SUM(credit) - SUM(debit)
    details_passif = LigneEcritureModel.objects.filter(
        compte__nature='PASSIF',
        compte__categorie='bilan',
        ecriture__exercice=exercice_courant
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
    ).annotate(
        solde=ExpressionWrapper(
            F('total_credit') - F('total_debit'),
            output_field=DecimalField()
        )
    ).filter(solde__gt=0).order_by('compte__code')

    total_actif = sum(item['solde'] for item in details_actif)
    total_passif = sum(item['solde'] for item in details_passif)

    context = {
        'actif': details_actif,
        'passif': details_passif,
        'total_actif': total_actif,
        'total_passif': total_passif,
        'resultat': total_actif - total_passif,
        'exercice_courant': exercice_courant,
        'date_bilan': date.today(),
    }
    return render(request, 'comptabilite/bilan.html', context)


@login_required
def compte_resultat(request):
    """Compte de résultat (produits / charges)"""

    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()

    # PRODUITS : nature='PRODUIT', solde = SUM(credit) - SUM(debit)
    details_produits = LigneEcritureModel.objects.filter(
        compte__nature='PRODUIT',
        compte__categorie='resultat',
        ecriture__exercice=exercice_courant
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
    ).annotate(
        solde=ExpressionWrapper(
            F('total_credit') - F('total_debit'),
            output_field=DecimalField()
        )
    ).filter(solde__gt=0).order_by('compte__code')

    # CHARGES : nature='CHARGE', solde = SUM(debit) - SUM(credit)
    details_charges = LigneEcritureModel.objects.filter(
        compte__nature='CHARGE',
        compte__categorie='resultat',
        ecriture__exercice=exercice_courant
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
    ).annotate(
        solde=ExpressionWrapper(
            F('total_debit') - F('total_credit'),
            output_field=DecimalField()
        )
    ).filter(solde__gt=0).order_by('compte__code')

    total_produits = sum(item['solde'] for item in details_produits)
    total_charges = sum(item['solde'] for item in details_charges)
    resultat = total_produits - total_charges

    if resultat > 0:
        resultat_texte = "Bénéfice net"
    elif resultat < 0:
        resultat_texte = "Perte nette"
    else:
        resultat_texte = "Équilibre"

    context = {
        'produits': details_produits,
        'charges': details_charges,
        'total_produits': total_produits,
        'total_charges': total_charges,
        'resultat': resultat,
        'resultat_texte': resultat_texte,
        'exercice_courant': exercice_courant,
    }
    return render(request, 'comptabilite/compte_resultat.html', context)


@login_required
def balance(request):
    """Balance générale (tous les comptes)"""

    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()

    # Récupérer les lignes groupées par compte
    lignes = LigneEcritureModel.objects.filter(
        ecriture__exercice=exercice_courant
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit')
    ).order_by('compte__code')

    lignes_list = []
    total_debit_sum = Decimal('0')
    total_credit_sum = Decimal('0')

    for ligne in lignes:
        debit = ligne['total_debit'] or Decimal('0')
        credit = ligne['total_credit'] or Decimal('0')
        total_debit_sum += debit
        total_credit_sum += credit

        # Calcul correct du solde : Débit - Crédit
        solde = debit - credit

        # Déterminer le sens du solde
        if solde > 0:
            solde_display = f"{solde:,.0f} F (D)"
            solde_class = "text-red-600"
        elif solde < 0:
            solde_display = f"{abs(solde):,.0f} F (C)"
            solde_class = "text-green-600"
        else:
            solde_display = "0 F"
            solde_class = "text-gray-400"

        lignes_list.append({
            'compte__code': ligne['compte__code'],
            'compte__libelle': ligne['compte__libelle'],
            'total_debit': debit,
            'total_credit': credit,
            'solde': solde,
            'solde_display': solde_display,
            'solde_class': solde_class,
        })

    # Écart = Débit - Crédit (doit être 0 pour une balance équilibrée)
    ecart = total_debit_sum - total_credit_sum

    context = {
        'lignes': lignes_list,
        'total_general_debit': total_debit_sum,
        'total_general_credit': total_credit_sum,
        'ecart': ecart,
        'exercice_courant': exercice_courant,
        'titre': 'Balance des comptes'
    }
    return render(request, 'comptabilite/balance.html', context)



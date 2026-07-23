from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Q
from decimal import Decimal
from ..models import ExerciceModel, EcritureModel, LigneEcritureModel


CASH_CODES = ['571', '5711', '5712', '5714', '521', '5211']


@login_required
def flux_tresorerie(request):
    """Tableau des flux de trésorerie (méthode directe)"""

    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()

    # Solde d'ouverture (avant le premier mouvement de l'exercice)
    solde_ouverture = Decimal('0')

    # Récupérer toutes les écritures concernant la trésorerie
    ecritures_cash = EcritureModel.objects.filter(
        lignes__compte__code__in=CASH_CODES,
        exercice=exercice_courant
    ).distinct().order_by('date_ecriture', 'id')

    # Catégories de flux
    flux_exploitation = []
    flux_investissement = []
    flux_financement = []

    total_entrees_exploitation = Decimal('0')
    total_sorties_exploitation = Decimal('0')
    total_entrees_investissement = Decimal('0')
    total_sorties_investissement = Decimal('0')
    total_entrees_financement = Decimal('0')
    total_sorties_financement = Decimal('0')

    for e in ecritures_cash:
        lignes = LigneEcritureModel.objects.filter(ecriture=e)
        cash_lignes = lignes.filter(compte__code__in=CASH_CODES)
        other_lignes = lignes.exclude(compte__code__in=CASH_CODES)

        for cl in cash_lignes:
            montant = cl.debit or cl.credit
            if montant == 0:
                continue

            est_entree = cl.debit > 0
            autres_codes = [l.compte.code for l in other_lignes if l.debit > 0 or l.credit > 0]

            # Déterminer la catégorie
            if est_entree:
                categorie = _categoriser_entree(e, autres_codes)
            else:
                categorie = _categoriser_sortie(e, autres_codes)

            item = {
                'date': e.date_ecriture,
                'libelle': e.libelle,
                'reference': e.reference,
                'montant': montant,
                'comptes_contrepartie': ', '.join(autres_codes),
            }

            if categorie == 'EXPLOITATION':
                flux_exploitation.append({**item, 'est_entree': est_entree})
                if est_entree:
                    total_entrees_exploitation += montant
                else:
                    total_sorties_exploitation += montant
            elif categorie == 'INVESTISSEMENT':
                flux_investissement.append({**item, 'est_entree': est_entree})
                if est_entree:
                    total_entrees_investissement += montant
                else:
                    total_sorties_investissement += montant
            elif categorie == 'FINANCEMENT':
                flux_financement.append({**item, 'est_entree': est_entree})
                if est_entree:
                    total_entrees_financement += montant
                else:
                    total_sorties_financement += montant

    # Totaux par catégorie
    flux_net_exploitation = total_entrees_exploitation - total_sorties_exploitation
    flux_net_investissement = total_entrees_investissement - total_sorties_investissement
    flux_net_financement = total_entrees_financement - total_sorties_financement

    variation_nette = flux_net_exploitation + flux_net_investissement + flux_net_financement

    # Solde de clôture
    solde_cloture = solde_ouverture + variation_nette

    context = {
        'exercice_courant': exercice_courant,
        'flux_exploitation': flux_exploitation,
        'flux_investissement': flux_investissement,
        'flux_financement': flux_financement,
        'total_entrees_exploitation': total_entrees_exploitation,
        'total_sorties_exploitation': total_sorties_exploitation,
        'flux_net_exploitation': flux_net_exploitation,
        'total_entrees_investissement': total_entrees_investissement,
        'total_sorties_investissement': total_sorties_investissement,
        'flux_net_investissement': flux_net_investissement,
        'total_entrees_financement': total_entrees_financement,
        'total_sorties_financement': total_sorties_financement,
        'flux_net_financement': flux_net_financement,
        'variation_nette': variation_nette,
        'solde_ouverture': solde_ouverture,
        'solde_cloture': solde_cloture,
        'titre': 'Tableau des flux de trésorerie',
        'header': 'Flux de trésorerie',
        'subtitle': 'Variation de la trésorerie (méthode directe)',
    }
    return render(request, 'comptabilite/flux_tresorerie.html', context)


def _categoriser_entree(ecriture, autres_codes):
    """Catégoriser une entrée de trésorerie"""
    journal = ecriture.journal.code if ecriture.journal else ''

    # Par journal
    if journal in ('VT', 'VN', 'CS', 'TR'):
        return 'EXPLOITATION'

    # Par contrepartie
    for code in autres_codes:
        if code.startswith('2'):
            return 'INVESTISSEMENT'  # Cession d'immobilisation
        if code.startswith('1'):
            return 'FINANCEMENT'     # Apport en capital, emprunt

    return 'EXPLOITATION'


def _categoriser_sortie(ecriture, autres_codes):
    """Catégoriser une sortie de trésorerie"""
    journal = ecriture.journal.code if ecriture.journal else ''

    # Par journal
    if journal in ('AC', 'CS', 'TR'):
        return 'EXPLOITATION'

    # Par contrepartie
    for code in autres_codes:
        if code.startswith('2'):
            return 'INVESTISSEMENT'  # Acquisition d'immobilisation
        if code.startswith('1'):
            return 'FINANCEMENT'     # Remboursement d'emprunt

    return 'EXPLOITATION'

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, F, DecimalField, ExpressionWrapper, Q
from decimal import Decimal
from ..models import ExerciceModel, CompteModel, LigneEcritureModel, JournalModel


@login_required
def grand_livre(request, compte_code=None):
    """Grand Livre : détail chronologique des mouvements par compte"""

    exercice_courant = ExerciceModel.objects.filter(cloture=False).first()
    if not exercice_courant:
        exercice_courant = ExerciceModel.objects.order_by('-date_debut').first()

    # Filtre par type de mouvement (journal)
    type_mvt = request.GET.get('type_mouvement', '')

    # Base filter : exercice courant
    base_filter = Q(ecriture__exercice=exercice_courant)
    if type_mvt:
        base_filter &= Q(ecriture__journal__code=type_mvt)

    # Tous les comptes avec solde pour le sélecteur / l'aperçu
    comptes_avec_solde = LigneEcritureModel.objects.filter(
        base_filter
    ).values('compte__code', 'compte__libelle').annotate(
        total_debit=Sum('debit'),
        total_credit=Sum('credit'),
    ).annotate(
        solde=ExpressionWrapper(
            F('total_debit') - F('total_credit'),
            output_field=DecimalField()
        )
    ).exclude(solde=0).order_by('compte__code')

    compte_selectionne = None
    lignes = []
    total_debit = Decimal('0')
    total_credit = Decimal('0')

    if compte_code:
        compte_selectionne = get_object_or_404(CompteModel, code=compte_code)
        lignes_filter = Q(
            compte=compte_selectionne,
            ecriture__exercice=exercice_courant
        )
        if type_mvt:
            lignes_filter &= Q(ecriture__journal__code=type_mvt)

        lignes_brutes = LigneEcritureModel.objects.filter(
            lignes_filter
        ).select_related('ecriture').order_by('ecriture__date_ecriture', 'ecriture__id')

        # Construire le détail avec solde cumulé
        solde_courant = Decimal('0')
        for l in lignes_brutes:
            solde_courant += l.debit - l.credit
            total_debit += l.debit
            total_credit += l.credit
            lignes.append({
                'date': l.ecriture.date_ecriture,
                'reference': l.ecriture.reference,
                'libelle': l.ecriture.libelle,
                'piece': l.ecriture.piece or '',
                'type_mouvement': l.ecriture.journal.code,
                'debit': l.debit,
                'credit': l.credit,
                'solde_cumule': solde_courant,
            })

        # Trouver le solde dans la liste des comptes
        solde_affiche = next(
            (c['solde'] for c in comptes_avec_solde if c['compte__code'] == compte_code),
            Decimal('0')
        )

    else:
        solde_affiche = None

    # Types de mouvements disponibles
    types_mouvements = JournalModel.objects.filter(actif=True).values_list('code', 'libelle')

    context = {
        'comptes': comptes_avec_solde,
        'compte_selectionne': compte_selectionne,
        'lignes': lignes,
        'solde_affiche': solde_affiche,
        'total_debit': total_debit if compte_code else 0,
        'total_credit': total_credit if compte_code else 0,
        'type_mouvement': type_mvt,
        'types_mouvements': types_mouvements,
        'exercice_courant': exercice_courant,
        'titre': 'Grand Livre',
        'header': 'Grand Livre',
        'subtitle': 'Détail chronologique des mouvements par compte',
    }
    return render(request, 'comptabilite/grand_livre.html', context)

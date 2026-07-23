from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from datetime import date
from ..services.dashboard_service import (
    get_tresorerie, get_ca_mensuel, get_charges_mensuelles,
    get_resultat, get_creances_clients, get_dettes_fournisseurs,
    get_depots_clients, get_evolution_ca_30j, get_ca_par_domaine,
    get_charges_par_domaine, get_dernieres_operations, get_alertes,
)


@login_required
def dashboard(request):
    tresorerie = get_tresorerie()
    ca = get_ca_mensuel()
    charges = get_charges_mensuelles()
    resultat = get_resultat(ca['ca_mois'], charges['charges_mois'])

    context = {
        'tresorerie': tresorerie,
        'ca': ca,
        'charges': charges,
        'resultat': resultat,
        'creances': get_creances_clients(),
        'dettes': get_dettes_fournisseurs(),
        'depots': get_depots_clients(),
        'evolution_ca': get_evolution_ca_30j(),
        'repartition_domaine': get_ca_par_domaine(),
        'charges_par_domaine': get_charges_par_domaine(),
        'dernieres_operations': get_dernieres_operations(),
        'alertes': get_alertes(),
        'date_aujourdhui': date.today(),
        'titre': 'Tableau de bord comptable',
    }

    return render(request, 'comptabilite/dashboard.html', context)

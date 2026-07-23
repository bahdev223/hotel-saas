def test():
    from apps.comptabilite.services.dashboard_service import (
        get_tresorerie, get_ca_mensuel, get_charges_mensuelles,
        get_resultat, get_creances_clients, get_dettes_fournisseurs,
        get_depots_clients, get_evolution_ca_30j, get_ca_par_domaine,
        get_dernieres_operations, get_alertes,
    )
    errors = []

    t = get_tresorerie()
    print(f"Tresorerie: total={t['total']}, caisses={t['total_caisses']}, banques={t['total_banques']}")
    if t['total'] < 0: errors.append("Tresorerie negative")

    ca = get_ca_mensuel()
    print(f"CA: jour={ca['ca_jour']}, mois={ca['ca_mois']}, evolution={ca['evolution']}%")

    c = get_charges_mensuelles()
    print(f"Charges: jour={c['charges_jour']}, mois={c['charges_mois']}")

    r = get_resultat(ca['ca_mois'], c['charges_mois'])
    print(f"Resultat: {r}")

    cre = get_creances_clients()
    print(f"Creances: {cre['nombre']} clients, {cre['total']} F")

    det = get_dettes_fournisseurs()
    print(f"Dettes: {det['nombre']} fournisseurs, {det['total']} F")

    d = get_depots_clients()
    print(f"Depots clients: {d}")

    evo = get_evolution_ca_30j()
    print(f"Evolution 30j: {len(evo)} jours")
    if evo:
        print(f"  Premier: {evo[0]}")
        print(f"  Dernier: {evo[-1]}")

    rep = get_ca_par_domaine()
    print(f"Repartition: hotel={rep['hotel']}, brasserie={rep['brasserie']}, restaurant={rep['restaurant']}")

    ops = get_dernieres_operations()
    print(f"Operations: {len(ops)} recentes")

    al = get_alertes()
    print(f"Alertes: {len(al)}")
    for a in al:
        print(f"  - [{a['type']}] {a['message']}")

    if errors:
        print(f"\nERRORS: {errors}")
        return 1
    print("\nALL OK")
    return 0


if __name__ == '__main__':
    import django, os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
    django.setup()
    sys.exit(test())

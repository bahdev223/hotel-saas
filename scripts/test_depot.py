def test():
    from decimal import Decimal
    from apps.comptabilite.services.ecriture_comptable import EcritureComptableService
    from apps.comptabilite.models import EcritureModel, LigneEcritureModel

    ecr = EcritureComptableService.creer_ecriture_depot_client(
        caisse=None, montant=Decimal('100000'),
        libelle='TEST depot client 100k',
        tiers_client=None,
    )

    print('=== DEPOT CLIENT ===')
    print(f'Reference: {ecr.reference}')
    print(f'Journal: {ecr.journal}')
    print(f'Libelle: {ecr.libelle}')
    print()

    lignes = LigneEcritureModel.objects.filter(ecriture=ecr)
    for l in lignes:
        typ = 'Debit' if l.debit else 'Credit'
        mt = l.debit or l.credit
        print(f'  {typ:8s} | {l.compte.code:6s} - {l.compte.libelle:<50s} | {mt:>10,.0f} F')

    debit_total = sum(l.debit for l in lignes)
    credit_total = sum(l.credit for l in lignes)
    print(f'  {"":8s}   {"":56s} {"---":>10s}')
    print(f'  {"":8s}   {"":56s} {debit_total:>10,.0f} F')
    print()
    ok = debit_total == credit_total
    print(f'Equilibre: {"OK" if ok else "KO"} {debit_total} = {credit_total}')
    print(f'Compte 571 present: {lignes.filter(compte__code="571").exists()}')
    print(f'Compte 419 present: {lignes.filter(compte__code="419").exists()}')

    ecr.delete()

    return ok and lignes.filter(compte__code="571").exists() and lignes.filter(compte__code="419").exists()


if __name__ == '__main__':
    import django
    import os, sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
    django.setup()
    sys.exit(0 if test() else 1)

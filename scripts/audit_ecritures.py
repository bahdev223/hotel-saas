"""
Audit des ecritures comptables existantes.
Verifie que les comptes utilises correspondent aux codes attendus.

Usage: python manage.py runscript audit_ecritures
   ou: python -X utf8 manage.py shell -c "exec(open('scripts/audit_ecritures.py').read())"
"""
import sys
from collections import Counter


EXPECTED_CODES = {
    '571': 'Caisse',
    '411': 'Clients',
    '419': 'Avances clients',
    '401': 'Fournisseurs',
    '521': 'Banque',
    '706': 'Prestations de services',
    '707': 'Ventes de marchandises',
    '658': 'Charges diverses',
}


def audit():
    from apps.comptabilite.models import EcritureModel, LigneEcritureModel

    ecritures = EcritureModel.objects.all().order_by('-date_ecriture')[:50]
    total = ecritures.count()
    incoherentes = 0

    print(f"=== AUDIT DES {total} DERNIERES ECRITURES ===\n")

    for ecr in ecritures:
        lignes = LigneEcritureModel.objects.filter(ecriture=ecr)
        problemes = []

        for ligne in lignes:
            compte = ligne.compte
            if compte is None:
                problemes.append(f"  LIGNE SANS COMPTE (debit={ligne.debit}, credit={ligne.credit})")
                continue

            expected_label = EXPECTED_CODES.get(compte.code)
            if expected_label:
                info = f"  {compte.code} - {compte.libelle}"
            else:
                info = f"  {compte.code} - {compte.libelle} (code non attendu)"

            if compte.code not in EXPECTED_CODES:
                info += " ⚠️"
                problemes.append(info)

        if problemes:
            incoherentes += 1
            print(f"[{ecr.reference}] {ecr.libelle[:60]}")
            print(f"  Journal: {ecr.journal}")
            print(f"  Date: {ecr.date_ecriture}")
            for p in problemes:
                print(p)
            print()

    print("=== RESUME ===")
    print(f"Total ecritures auditees: {total}")
    print(f"Ecritures avec incoherences: {incoherentes}")
    print(f"Ecritures coherentes: {total - incoherentes}")

    # Analyse des comptes les plus utilises
    compte_counts = Counter()
    for ecr in ecritures:
        for ligne in LigneEcritureModel.objects.filter(ecriture=ecr):
            if ligne.compte:
                compte_counts[ligne.compte.code] += 1

    print("\n=== COMPTES LES PLUS UTILISES ===")
    for code, count in compte_counts.most_common(15):
        expected = EXPECTED_CODES.get(code)
        flag = " ✅" if expected else " ⚠️"
        print(f"  {code}: {count}x{flag}")

    return incoherentes


if __name__ == '__main__':
    import django
    import os
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    django.setup()
    sys.exit(audit())

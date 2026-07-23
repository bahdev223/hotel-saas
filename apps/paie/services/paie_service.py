from decimal import Decimal
from datetime import date
from django.db import transaction
from ..models import PeriodePaie, BulletinPaie, LigneBulletinPaie, RubriquePaie
from apps.rh.models import Employe


class PaieService:
    """ Service de calcul de paie """

    @classmethod
    @transaction.atomic
    def generer_bulletin(cls, employe_id, periode_id):
        """ Génère un bulletin pour un employé """

        employe = Employe.objects.get(id=employe_id)
        periode = PeriodePaie.objects.get(id=periode_id)

        salaire_base = employe.salaire_fixe

        # Récupérer les rubriques
        rubrique_base = RubriquePaie.objects.get(code='BASE')
        rubrique_cnss = RubriquePaie.objects.get(code='CNSS')
        rubrique_amo = RubriquePaie.objects.get(code='AMO')
        rubrique_its = RubriquePaie.objects.get(code='ITS')
        rubrique_avance = RubriquePaie.objects.get_or_create(
            code='AVANCE',
            defaults={'libelle': 'Remboursement avance', 'type_rubrique': 'RETENUE', 'sens': 'NET', 'ordre': 40, 'actif': True}
        )[0]

        # Créer ou récupérer le bulletin
        bulletin, created = BulletinPaie.objects.get_or_create(
            employe=employe,
            periode=periode,
            defaults={
                'numero': f"BUL-{periode.annee}{periode.mois:02d}-{employe.matricule}",
                'base_calcul': salaire_base,
                'statut': 'CALCULE'
            }
        )

        if not created:
            bulletin.lignes.all().delete()

        # Salaire de base
        LigneBulletinPaie.objects.create(
            bulletin=bulletin,
            rubrique=rubrique_base,
            base=salaire_base,
            taux=100,
            montant=salaire_base,
            ordre=10
        )

        total_brut = salaire_base

        # CNSS (3.6%)
        cnss = salaire_base * Decimal('0.036')
        LigneBulletinPaie.objects.create(
            bulletin=bulletin,
            rubrique=rubrique_cnss,
            base=salaire_base,
            taux=3.6,
            montant=cnss,
            ordre=20
        )

        # AMO (5%)
        amo = salaire_base * Decimal('0.05')
        LigneBulletinPaie.objects.create(
            bulletin=bulletin,
            rubrique=rubrique_amo,
            base=salaire_base,
            taux=5,
            montant=amo,
            ordre=25
        )

        total_cotisations = cnss + amo

        # ITS
        its = cls._calculer_its(salaire_base)
        LigneBulletinPaie.objects.create(
            bulletin=bulletin,
            rubrique=rubrique_its,
            base=salaire_base,
            taux=0,
            montant=its,
            ordre=30
        )

        # Remboursements avances
        remboursement_total, lignes_remb = cls._get_remboursements_mois(employe, periode.annee, periode.mois)

        if remboursement_total > 0:
            LigneBulletinPaie.objects.create(
                bulletin=bulletin,
                rubrique=rubrique_avance,
                base=remboursement_total,
                taux=100,
                montant=remboursement_total,
                ordre=40
            )
            for ligne in lignes_remb:
                ligne.rembourse = True
                ligne.bulletin = bulletin
                ligne.date_remboursement = date.today()
                ligne.save()

        net_a_payer = total_brut - total_cotisations - its - remboursement_total

        bulletin.base_calcul = salaire_base
        bulletin.total_brut = total_brut
        bulletin.total_cotisations = total_cotisations
        bulletin.total_impots = its
        bulletin.net_a_payer = net_a_payer
        bulletin.statut = 'CALCULE'
        bulletin.save()

        cls._generer_ecritures_comptables(bulletin, salaire_base, cnss, amo, its, net_a_payer)

        return bulletin

    @classmethod
    def _calculer_its(cls, salaire_brut):
        """ Barème ITS """
        if salaire_brut <= 50000:
            return Decimal('0')
        elif salaire_brut <= 100000:
            return (salaire_brut - 50000) * Decimal('0.10')
        elif salaire_brut <= 200000:
            return Decimal('5000') + (salaire_brut - 100000) * Decimal('0.15')
        elif salaire_brut <= 500000:
            return Decimal('20000') + (salaire_brut - 200000) * Decimal('0.25')
        else:
            return Decimal('95000') + (salaire_brut - 500000) * Decimal('0.35')

    @classmethod
    def generer_tous_bulletins(cls, periode_id):
        """ Génère les bulletins pour tous les employés actifs """
        employes = Employe.objects.filter(actif=True)
        resultats = []

        for employe in employes:
            try:
                bulletin = cls.generer_bulletin(employe.id, periode_id)
                resultats.append({
                    'employe': f"{employe.nom} {employe.prenom}",
                    'net': bulletin.net_a_payer,
                    'success': True
                })
            except Exception as e:
                resultats.append({
                    'employe': f"{employe.nom} {employe.prenom}",
                    'error': str(e),
                    'success': False
                })

        return resultats

    @classmethod
    def _get_remboursements_mois(cls, employe, annee, mois):
        """Récupère les remboursements d'avance pour un employé pour un mois donné"""
        from ..models import LigneRemboursement

        lignes = LigneRemboursement.objects.filter(
            avance__employe=employe,
            annee=annee,
            mois=mois,
            rembourse=False,
            avance__statut='PAYEE'
        )

        total_remboursement = sum(l.montant for l in lignes)

        return total_remboursement, lignes

    @classmethod
    def _generer_ecritures_comptables(cls, bulletin, salaire_base, cnss, amo, its, net_a_payer):
        """ Génère les écritures comptables pour le bulletin """
        from apps.comptabilite.models import EcritureComptable, ExerciceComptable, CompteComptable

        exercice = ExerciceComptable.objects.filter(actif=True).first()
        if not exercice:
            return

        compte_salaire = CompteComptable.objects.filter(numero__startswith='641').first()
        compte_cnss = CompteComptable.objects.filter(numero__startswith='431').first()
        compte_amo = CompteComptable.objects.filter(numero__startswith='432').first()
        compte_its = CompteComptable.objects.filter(numero__startswith='442').first()
        compte_banque = CompteComptable.objects.filter(numero__startswith='512').first()

        if all([compte_salaire, compte_cnss, compte_amo, compte_its, compte_banque]):
            EcritureComptable.objects.create(
                exercice=exercice,
                bulletin=bulletin,
                compte=compte_salaire,
                libelle=f"Salaire {bulletin.employe.nom_complet} - {bulletin.periode.mois}/{bulletin.periode.annee}",
                debit=salaire_base,
                credit=Decimal('0.00'),
                date_ecriture=date.today()
            )
            EcritureComptable.objects.create(
                exercice=exercice,
                bulletin=bulletin,
                compte=compte_cnss,
                libelle=f"CNSS {bulletin.employe.nom_complet}",
                debit=Decimal('0.00'),
                credit=cnss,
                date_ecriture=date.today()
            )
            EcritureComptable.objects.create(
                exercice=exercice,
                bulletin=bulletin,
                compte=compte_amo,
                libelle=f"AMO {bulletin.employe.nom_complet}",
                debit=Decimal('0.00'),
                credit=amo,
                date_ecriture=date.today()
            )
            EcritureComptable.objects.create(
                exercice=exercice,
                bulletin=bulletin,
                compte=compte_its,
                libelle=f"ITS {bulletin.employe.nom_complet}",
                debit=Decimal('0.00'),
                credit=its,
                date_ecriture=date.today()
            )
            EcritureComptable.objects.create(
                exercice=exercice,
                bulletin=bulletin,
                compte=compte_banque,
                libelle=f"Net {bulletin.employe.nom_complet}",
                debit=Decimal('0.00'),
                credit=net_a_payer,
                date_ecriture=date.today()
            )

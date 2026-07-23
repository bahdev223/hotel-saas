from decimal import Decimal
from django.db import transaction
from django.utils import timezone


class StockComptaError(Exception):
    pass


class StockComptaService:
    """Cree un mouvement de stock + son ecriture comptable en une transaction"""

    COMPTES_PAR_DEFAUT = {
        ('ENTREE', 'achat'): {'debit': '31', 'credit': '401'},
        ('ENTREE', 'production'): {'debit': '31', 'credit': '31'},
        ('ENTREE', 'reapprovisionnement'): {'debit': '31', 'credit': '401'},
        ('ENTREE', 'inventaire'): {'debit': '31', 'credit': '603'},
        ('SORTIE', 'vente'): {'debit': '411', 'credit': '701'},
        ('SORTIE', 'consommation'): {'debit': '601', 'credit': '31'},
        ('SORTIE', 'perte'): {'debit': '658', 'credit': '31'},
        ('SORTIE', 'production'): {'debit': '601', 'credit': '31'},
        ('SORTIE', 'inventaire'): {'debit': '603', 'credit': '31'},
        ('INITIALISATION', 'stock_initial'): {'debit': None, 'credit': None},
    }

    COMPTE_STOCK_PAR_TYPE = {
        'MARCHANDISE': '31',
        'MATIERE_PREMIERE': '32',
        'CONSOMMABLE': '33',
        'EMBALLAGE': '33',
    }

    @staticmethod
    @transaction.atomic
    def enregistrer_mouvement(produit, type_mouvement, motif, quantite,
                              valeur_unitaire=0, entrepot_source=None,
                              entrepot_dest=None, reference='',
                              raison='', utilisateur='', lot=None,
                              unite_texte=''):
        """Cree le MouvementStock + l'Ecriture comptable"""

        from ..models import MouvementStock

        valeur_total = Decimal(str(quantite)) * Decimal(str(valeur_unitaire))

        mouvement = MouvementStock.objects.create(
            produit=produit, type_mouvement=type_mouvement, motif=motif,
            quantite=quantite, valeur_unitaire=valeur_unitaire,
            valeur_total=valeur_total, entrepot_source=entrepot_source,
            entrepot_dest=entrepot_dest, reference=reference,
            raison=raison, utilisateur=utilisateur,
            unite_texte=unite_texte,
        )

        comptes = StockComptaService.COMPTES_PAR_DEFAUT.get((type_mouvement, motif))
        if comptes and valeur_total > 0:
            # Résoudre le compte de débit
            debit = comptes['debit']
            if debit is None:
                debit = StockComptaService.COMPTE_STOCK_PAR_TYPE.get(produit.type_article, '31')

            # Résoudre le compte de crédit
            credit = comptes['credit']
            if credit is None:
                from apps.comptabilite.models.configuration import ParametreEntreprise
                credit = ParametreEntreprise.get_compte_contrepartie()

            StockComptaService._creer_ecriture(mouvement, {'debit': debit, 'credit': credit})

        return mouvement

    @staticmethod
    def _creer_ecriture(mouvement, comptes):
        """Cree une ecriture comptable liee au mouvement"""
        from apps.comptabilite.models.ecriture import EcritureModel, LigneEcritureModel
        from apps.comptabilite.models.journal import JournalModel
        from apps.comptabilite.models.exercice import ExerciceModel
        from apps.comptabilite.models.compte import CompteModel

        today = timezone.now().date()

        if mouvement.type_mouvement == 'INITIALISATION' or mouvement.motif == 'inventaire':
            journal_code = 'OD'
        elif mouvement.type_mouvement == 'ENTREE':
            journal_code = 'ACH'
        else:
            journal_code = 'VTE'

        journal, _ = JournalModel.objects.get_or_create(code=journal_code, defaults={'libelle': journal_code, 'type_journal': 'OD'})

        exercice = ExerciceModel.objects.filter(date_debut__lte=today, date_fin__gte=today).first()
        if not exercice:
            exercice = ExerciceModel.objects.create(
                code=str(today.year), date_debut=today.replace(month=1, day=1),
                date_fin=today.replace(month=12, day=31)
            )

        ref = f"MVT-{timezone.now().strftime('%y%m%d%H%M%S')}-{mouvement.id}"
        ecriture = EcritureModel.objects.create(
            reference=ref,
            date_ecriture=today,
            libelle=f"{mouvement.get_motif_display()} - {mouvement.produit.nom} - {mouvement.raison}",
            journal=journal, exercice=exercice,
            created_by=mouvement.utilisateur,
        )

        compte_debit = CompteModel.objects.filter(code__startswith=comptes['debit'], actif=True).first()
        compte_credit = CompteModel.objects.filter(code__startswith=comptes['credit'], actif=True).first()

        if not compte_debit and not compte_credit:
            raise StockComptaError(
                f"Aucun compte trouvé pour l'écriture {mouvement.type_mouvement}/{mouvement.motif}: "
                f"debit={comptes['debit']}, credit={comptes['credit']}. "
                f"Vérifiez le plan comptable."
            )

        if compte_debit and mouvement.valeur_total > 0:
            LigneEcritureModel.objects.create(
                ecriture=ecriture, compte=compte_debit,
                debit=mouvement.valeur_total, libelle=ecriture.libelle
            )
        if compte_credit and mouvement.valeur_total > 0:
            LigneEcritureModel.objects.create(
                ecriture=ecriture, compte=compte_credit,
                credit=mouvement.valeur_total, libelle=ecriture.libelle
            )

        mouvement.ecriture = ecriture
        mouvement.save(update_fields=['ecriture'])

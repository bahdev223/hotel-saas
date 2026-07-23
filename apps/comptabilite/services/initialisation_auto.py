from decimal import Decimal
from datetime import date, datetime
from django.db import transaction
from django.db.models import Sum, F
from django.utils import timezone
from django.contrib.auth.models import User

from ..models import (
    ConfigurationEntreprise, ExerciceModel, JournalModel,
    CompteModel, EcritureModel, LigneEcritureModel,
    CompteClient, CompteFournisseur
)
from apps.tresorerie.models import Caisse
from apps.stock.models import StockEntrepot, Inventaire, LigneInventaire


class InitialisationAutoService:
    """Assistant de mise en service — construit la situation initiale du logiciel"""

    # ─── Helpers ───────────────────────────────────────────────

    @staticmethod
    def get_or_create_exercice():
        """Retourne l'exercice courant, le crée si aucun n'existe"""
        today = date.today()
        exercice = ExerciceModel.objects.filter(
            date_debut__lte=today, date_fin__gte=today, cloture=False
        ).first()
        if exercice:
            return exercice
        exercice = ExerciceModel.objects.filter(cloture=False).first()
        if exercice:
            return exercice
        annee = today.year
        return ExerciceModel.objects.create(
            code=str(annee),
            date_debut=date(annee, 1, 1),
            date_fin=date(annee, 12, 31),
            cloture=False,
        )

    @staticmethod
    def get_config():
        config = ConfigurationEntreprise.objects.first()
        if not config:
            config = ConfigurationEntreprise.objects.create(nom="Mon Entreprise")
        return config

    @staticmethod
    def _get_compte(code_or_id):
        if code_or_id is None:
            return None
        if isinstance(code_or_id, int):
            return CompteModel.objects.filter(id=code_or_id, actif=True).first()
        compte = CompteModel.objects.filter(code=code_or_id, actif=True).first()
        if compte is not None:
            return compte
        if isinstance(code_or_id, str) and code_or_id.isdigit():
            return CompteModel.objects.filter(id=int(code_or_id), actif=True).first()
        return None

    # ─── Détection des données ─────────────────────────────────

    @staticmethod
    def get_stocks():
        """Stock par entrepôt — premier inventaire validé uniquement"""
        entrepots = []
        total = Decimal('0')
        for entrepot in Inventaire.objects.filter(statut='VALIDE') \
                .values_list('entrepot', flat=True).distinct():
            # Premier inventaire validé pour cet entrepôt
            premier = Inventaire.objects.filter(
                entrepot=entrepot, statut='VALIDE'
            ).order_by('date_fin', 'id').first()
            if not premier:
                continue
            lignes = LigneInventaire.objects.filter(inventaire=premier)
            valeur = Decimal('0')
            for l in lignes:
                pu = Decimal(str(l.prix_unitaire or l.produit.prix_achat or 0))
                valeur += Decimal(str(l.quantite_reelle or 0)) * pu
            entrepots.append({
                'entrepot_id': premier.entrepot_id,
                'entrepot_nom': premier.entrepot.nom if hasattr(premier.entrepot, 'nom') else str(premier.entrepot),
                'entrepot_code': premier.entrepot.code if hasattr(premier.entrepot, 'code') else '',
                'inventaire_code': premier.code,
                'inventaire_date': premier.date_fin,
                'est_premier': not Inventaire.objects.filter(
                    entrepot=entrepot, statut='VALIDE'
                ).exclude(id=premier.id).exists(),
                'valeur': float(valeur),
            })
            total += valeur
        return {
            'total': float(total),
            'ok': len(entrepots) > 0,
            'entrepots': entrepots,
        }

    @staticmethod
    def get_tresorerie():
        """Comptes financiers actifs avec leurs soldes"""
        caisses = Caisse.objects.filter(actif=True).order_by('type_financier', 'code')
        comptes = []
        total_especes = Decimal('0')
        total_banque = Decimal('0')
        total_mobile = Decimal('0')
        for c in caisses:
            s = c.solde or Decimal('0')
            comptes.append({
                'id': c.id,
                'code': c.code,
                'nom': c.nom,
                'type_financier': c.type_financier,
                'role': c.role,
                'solde': float(s),
                'compte_comptable': c.compte_comptable.code if c.compte_comptable else None,
            })
            if c.type_financier == 'ESPECES':
                total_especes += s
            elif c.type_financier == 'BANQUE':
                total_banque += s
            elif c.type_financier == 'MOBILE_MONEY':
                total_mobile += s
        return {
            'total': float(total_especes + total_banque + total_mobile),
            'total_especes': float(total_especes),
            'total_banque': float(total_banque),
            'total_mobile': float(total_mobile),
            'ok': comptes and len(comptes) > 0,
            'comptes': comptes,
        }

    @staticmethod
    def get_creances():
        """Créances clients (CompteClient.solde > 0)"""
        comptes = CompteClient.objects.filter(solde__gt=0)
        total = sum(c.solde for c in comptes)
        return {
            'total': float(total),
            'ok': total > 0,
            'nombre': comptes.count(),
        }

    @staticmethod
    def get_dettes():
        """Dettes fournisseurs (CompteFournisseur.solde > 0)"""
        comptes = CompteFournisseur.objects.filter(solde__gt=0)
        total = sum(c.solde for c in comptes)
        return {
            'total': float(total),
            'ok': total > 0,
            'nombre': comptes.count(),
        }

    # ─── État d'avancement ─────────────────────────────────────

    def get_etat_avancement(self):
        config = self.get_config()
        stocks = self.get_stocks()
        tresorerie = self.get_tresorerie()
        creances = self.get_creances()
        dettes = self.get_dettes()

        # Progression
        points = 0
        max_points = 2  # stocks + tresorerie sont obligatoires
        if stocks['ok']:
            points += 1
        if tresorerie['ok']:
            points += 1
        prete_a_valider = stocks['ok'] and tresorerie['ok']
        progression = int((points / max_points) * 100) if max_points else 0

        return {
            'stocks': stocks,
            'tresorerie': tresorerie,
            'creances': creances,
            'dettes': dettes,
            'prete_a_valider': prete_a_valider,
            'progression': progression,
            'deja_validee': config.situation_initiale_validee,
            'date_validation': config.date_validation_situation,
            'contrepartie': config.contrepartie_situation,
            'mode_demarrage': config.mode_demarrage,
        }

    # ─── Aperçu écriture ───────────────────────────────────────

    def get_apercu_ecriture(self, contrepartie_code='101'):
        """Retourne les lignes d'écriture qui seront générées"""
        stocks = self.get_stocks()
        tresorerie = self.get_tresorerie()
        creances = self.get_creances()
        dettes = self.get_dettes()

        lignes_debit = []
        total_debit = Decimal('0')

        if tresorerie['total_especes'] > 0:
            lignes_debit.append({
                'compte_code': '57',
                'compte_libelle': 'Caisse',
                'montant': tresorerie['total_especes'],
            })
            total_debit += Decimal(str(tresorerie['total_especes']))
        if tresorerie['total_banque'] > 0:
            lignes_debit.append({
                'compte_code': '52',
                'compte_libelle': 'Banque',
                'montant': tresorerie['total_banque'],
            })
            total_debit += Decimal(str(tresorerie['total_banque']))
        if tresorerie['total_mobile'] > 0:
            lignes_debit.append({
                'compte_code': '58',
                'compte_libelle': 'Mobile Money',
                'montant': tresorerie['total_mobile'],
            })
            total_debit += Decimal(str(tresorerie['total_mobile']))
        if stocks['total'] > 0:
            lignes_debit.append({
                'compte_code': '31',
                'compte_libelle': 'Stocks',
                'montant': stocks['total'],
            })
            total_debit += Decimal(str(stocks['total']))
        if creances['total'] > 0:
            lignes_debit.append({
                'compte_code': '411',
                'compte_libelle': 'Clients',
                'montant': creances['total'],
            })
            total_debit += Decimal(str(creances['total']))

        lignes_credit = []
        total_credit = Decimal('0')

        if dettes['total'] > 0:
            lignes_credit.append({
                'compte_code': '401',
                'compte_libelle': 'Fournisseurs',
                'montant': dettes['total'],
            })
            total_credit += Decimal(str(dettes['total']))

        capital = total_debit - total_credit
        contrepartie = self._get_compte(contrepartie_code)
        lignes_credit.append({
            'compte_code': contrepartie_code,
            'compte_libelle': contrepartie.libelle if contrepartie else 'Contrepartie',
            'montant': float(capital),
        })
        total_credit += capital

        return {
            'equilibre': total_debit == total_credit,
            'total_debit': float(total_debit),
            'total_credit': float(total_credit),
            'capital': float(capital),
            'lignes_debit': lignes_debit,
            'lignes_credit': lignes_credit,
        }

    # ─── Validation ────────────────────────────────────────────

    @transaction.atomic
    def valider_situation(self, contrepartie_code='101', user=None):
        config = self.get_config()
        if config.situation_initiale_validee:
            return {'success': False, 'error': 'Situation déjà validée'}

        stocks = self.get_stocks()
        tresorerie = self.get_tresorerie()
        if not stocks['ok'] or not tresorerie['ok']:
            return {'success': False, 'error': 'Stocks et trésorerie requis'}

        exercice = self.get_or_create_exercice()
        apercu = self.get_apercu_ecriture(contrepartie_code)

        # Journal OD
        journal, _ = JournalModel.objects.get_or_create(
            code='OD',
            defaults={'libelle': 'Opérations Diverses', 'type_journal': 'OD', 'actif': True}
        )

        # Référence
        now = timezone.now()
        existing = EcritureModel.objects.filter(
            reference__startswith=f'OUV-{exercice.code}'
        ).count()
        seq = f"{existing + 1:04d}"
        reference = f"OUV-{exercice.code}-{seq}"

        # Créer l'écriture
        ecriture = EcritureModel.objects.create(
            reference=reference,
            date_ecriture=now.date(),
            libelle=f"Écriture d'ouverture — Exercice {exercice.code}",
            journal=journal,
            piece=f"SITUATION-INITIALE-{seq}",
            exercice=exercice,
            validee=True,
            date_validation=now,
            created_by=user.username if hasattr(user, 'username') and user else 'system',
        )

        # Lignes débit (actif)
        for ligne in apercu['lignes_debit']:
            compte = self._get_compte(ligne['compte_code'])
            if compte:
                LigneEcritureModel.objects.create(
                    ecriture=ecriture,
                    compte=compte,
                    debit=ligne['montant'],
                    credit=0,
                    libelle=f"Situation initiale — {ligne['compte_libelle']}",
                )

        # Lignes crédit (passif)
        for ligne in apercu['lignes_credit']:
            compte = self._get_compte(ligne['compte_code'])
            if compte:
                LigneEcritureModel.objects.create(
                    ecriture=ecriture,
                    compte=compte,
                    debit=0,
                    credit=ligne['montant'],
                    libelle=f"Situation initiale — {ligne['compte_libelle']}",
                )

        # Marquer la configuration
        config.situation_initiale_validee = True
        config.date_validation_situation = now
        config.contrepartie_situation = contrepartie_code
        config.mode_demarrage = False
        config.save()

        return {
            'success': True,
            'reference': reference,
            'ecriture_id': ecriture.id,
            'date_validation': now,
        }

    # ─── Écriture d'ouverture existante ─────────────────────────

    def get_ecriture_existante(self):
        exercice = self.get_or_create_exercice()
        return EcritureModel.objects.filter(
            reference__startswith=f'OUV-{exercice.code}'
        ).order_by('-created_at').first()

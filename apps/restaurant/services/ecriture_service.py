# apps/restaurant/services/ecriture_service.py
from decimal import Decimal
from datetime import date
from django.db import transaction
from apps.comptabilite.models import (
    EcritureModel, LigneEcritureModel, JournalModel,
    CompteModel, ExerciceModel
)
from apps.tresorerie.services import MouvementService
from apps.tresorerie.models import Caisse


class EcritureRestaurantService:
    """Service comptable automatique pour le restaurant"""

    @classmethod
    @transaction.atomic
    def enregistrer_vente(cls, vente, utilisateur, caisse, mode_paiement="ESPECES"):
        """
        Vente restaurant payée immédiatement (cash / carte / mobile)
        
        Débit: 57xx (caisse associée)
        Crédit: 701 (Ventes restaurant)
        + Mouvement de trésorerie tracé
        """
        if not caisse:
            raise ValueError("Caisse obligatoire")

        if not caisse.actif:
            raise ValueError(f"La caisse {caisse.code} est inactive")

        exercice = cls._get_exercice_courant()

        journal, _ = JournalModel.objects.get_or_create(
            code="VN",
            defaults={'libelle': 'Ventes', 'type_journal': 'VENTES', 'actif': True}
        )

        reference = f"RESTO-VTE-{vente.id}-{date.today().strftime('%Y%m%d%H%M%S')}"

        # 1. Créer l'écriture comptable
        ecriture = EcritureModel.objects.create(
            reference=reference,
            date_ecriture=date.today(),
            libelle=f"Vente restaurant #{vente.id}",
            journal=journal,
            piece=f"RESTO-{vente.id}",
            exercice=exercice,
            validee=True,
            created_by=utilisateur.username if hasattr(utilisateur, 'username') else str(utilisateur)
        )

        # Récupérer les comptes
        compte_caisse = caisse.compte_comptable
        compte_vente = cls._get_compte("701")  # Ventes restaurant

        # Lignes d'écriture (Débit Caisse / Crédit Vente)
        LigneEcritureModel.objects.create(
            ecriture=ecriture,
            compte=compte_caisse,
            debit=vente.montant_total,
            credit=0,
            libelle=f"Vente restaurant #{vente.id}"
        )

        LigneEcritureModel.objects.create(
            ecriture=ecriture,
            compte=compte_vente,
            debit=0,
            credit=vente.montant_total,
            libelle=f"Vente restaurant #{vente.id}"
        )

        # Vérifier l'équilibre de l'écriture
        if not cls._ecriture_equilibree(ecriture):
            raise ValueError("Écriture non équilibrée")

        # 2. Mouvement de trésorerie (trace l'entrée d'argent)
        MouvementService.encaisser(
            caisse=caisse,
            montant=vente.montant_total,
            libelle=f"Vente restaurant #{vente.id}",
            user=utilisateur,
            reference=reference
        )

        print(f"✅ Vente restaurant #{vente.id} - {vente.montant_total:,.0f} F - Caisse: {caisse.code}")
        return ecriture

    @classmethod
    def enregistrer_achat(cls, achat, utilisateur):
        """Écriture automatique pour un achat restaurant"""
        
        exercice = cls._get_exercice_courant()

        journal, _ = JournalModel.objects.get_or_create(
            code="AC",
            defaults={'libelle': 'Achats', 'type_journal': 'ACHATS', 'actif': True}
        )

        reference = f"RESTO-ACH-{achat.id}-{date.today().strftime('%Y%m%d%H%M%S')}"

        ecriture = EcritureModel.objects.create(
            reference=reference,
            date_ecriture=date.today(),
            libelle=f"Achat restaurant #{achat.numero}",
            journal=journal,
            piece=achat.numero,
            exercice=exercice,
            validee=True,
            created_by=utilisateur.username if hasattr(utilisateur, 'username') else str(utilisateur)
        )

        compte_achat = cls._get_compte("601")
        compte_fournisseur = cls._get_compte("401")

        LigneEcritureModel.objects.create(
            ecriture=ecriture,
            compte=compte_achat,
            debit=achat.montant_total,
            credit=0,
            libelle=f"Achat #{achat.numero}"
        )

        LigneEcritureModel.objects.create(
            ecriture=ecriture,
            compte=compte_fournisseur,
            debit=0,
            credit=achat.montant_total,
            libelle=f"Fournisseur"
        )

        if not cls._ecriture_equilibree(ecriture):
            raise ValueError("Écriture non équilibrée")

        print(f"✅ Écriture achat {reference} créée")
        return ecriture

    @classmethod
    def _get_exercice_courant(cls):
        """Récupère ou crée l'exercice comptable courant"""
        exercice = ExerciceModel.objects.filter(
            date_debut__lte=date.today(),
            date_fin__gte=date.today(),
            cloture=False
        ).first()

        if not exercice:
            annee = date.today().year
            exercice = ExerciceModel.objects.create(
                code=str(annee),
                date_debut=date(annee, 1, 1),
                date_fin=date(annee, 12, 31),
                cloture=False
            )
            print(f"✅ Exercice {annee} créé automatiquement")

        return exercice

    @classmethod
    def _get_compte(cls, code):
        """Récupère un compte comptable avec vérification"""
        compte = CompteModel.objects.filter(code=code).first()
        if not compte:
            raise ValueError(f"Compte comptable {code} introuvable")
        return compte

    @classmethod
    def _ecriture_equilibree(cls, ecriture):
        """Vérifie si l'écriture est équilibrée (débit = crédit)"""
        lignes = ecriture.lignes.all()
        total_debit = sum(l.debit for l in lignes)
        total_credit = sum(l.credit for l in lignes)
        return total_debit == total_credit
    
    
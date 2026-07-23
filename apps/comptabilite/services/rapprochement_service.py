# apps/comptabilite/services/rapprochement_service.py
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Q, Sum
from ..models import ReleveBancaire, LigneReleveBancaire, EcartRapprochement
from apps.tresorerie.models import MouvementCaisse


class RapprochementService:
    """Service de rapprochement bancaire"""
    
    @classmethod
    @transaction.atomic
    def importer_releve(cls, caisse, date_debut, date_fin, lignes_data, user):
        """Importe un relevé bancaire"""
        
        # Créer le relevé
        releve = ReleveBancaire.objects.create(
            caisse=caisse,
            date_debut=date_debut,
            date_fin=date_fin,
            solde_ouverture=cls._calculer_solde_ouverture(caisse, date_debut),
            solde_cloture=0,  # Sera calculé
            statut='BROUILLON',
            created_by=user
        )
        
        # Ajouter les lignes
        total_credit = Decimal('0')
        total_debit = Decimal('0')
        
        for ligne_data in lignes_data:
            ligne = LigneReleveBancaire.objects.create(
                releve=releve,
                date_operation=ligne_data['date'],
                libelle=ligne_data['libelle'],
                montant=ligne_data['montant'],
                sens=ligne_data['sens'],
                reference=ligne_data.get('reference', '')
            )
            
            if ligne.sens == 'CREDIT':
                total_credit += ligne.montant
            else:
                total_debit += ligne.montant
        
        # Calculer solde de clôture
        releve.solde_cloture = releve.solde_ouverture + total_credit - total_debit
        releve.save()
        
        return releve
    
    @classmethod
    def _calculer_solde_ouverture(cls, caisse, date_debut):
        """Calcule le solde de la caisse à une date donnée"""
        mouvements = MouvementCaisse.objects.filter(
            caisse=caisse,
            date__date__lt=date_debut
        )
        
        total_entrees = mouvements.filter(type_mouvement='ENTREE').aggregate(total=Sum('montant'))['total'] or 0
        total_sorties = mouvements.filter(type_mouvement='SORTIE').aggregate(total=Sum('montant'))['total'] or 0
        
        return total_entrees - total_sorties
    
    @classmethod
    def rapprocher_ligne(cls, ligne_id, ecriture_id, user):
        """Rapproche une ligne de relevé avec une écriture"""
        ligne = LigneReleveBancaire.objects.get(id=ligne_id)
        
        if ligne.statut == 'RAPPROCHE':
            raise ValueError("Cette ligne est déjà rapprochée")
        
        ligne.statut = 'RAPPROCHE'
        ligne.ecriture_rapprochee_id = ecriture_id
        ligne.save()
        
        return ligne
    
    @classmethod
    def creer_ecart(cls, releve_id, type_ecart, montant, sens, justification, user):
        """Crée un écart de rapprochement et génère l'écriture corrective"""
        from ..models import EcritureModel, LigneEcritureModel, JournalModel, ExerciceModel, CompteModel
        
        releve = ReleveBancaire.objects.get(id=releve_id)
        
        # Récupérer l'exercice
        exercice = ExerciceModel.objects.filter(
            date_debut__lte=releve.date_fin,
            date_fin__gte=releve.date_fin,
            cloture=False
        ).first()
        
        # Créer l'écriture corrective
        journal, _ = JournalModel.objects.get_or_create(
            code="OD",
            defaults={'libelle': 'Opérations Diverses', 'type_journal': 'OD', 'actif': True}
        )
        
        reference = f"ECART-{releve.id}-{int(montant)}"
        
        ecriture = EcritureModel.objects.create(
            reference=reference,
            date_ecriture=releve.date_fin,
            libelle=f"Écart rapprochement - {justification[:100]}",
            journal=journal,
            exercice=exercice,
            validee=True,
            created_by=user.username if hasattr(user, 'username') else str(user)
        )
        
        # Déterminer les comptes
        if type_ecart == 'COMMISSION':
            compte = CompteModel.objects.get(code='628')  # Services bancaires
        elif type_ecart == 'INTERET':
            compte = CompteModel.objects.get(code='661')  # Intérêts
        else:
            compte = CompteModel.objects.get(code='671')  # Pertes diverses
        
        compte_caisse = releve.caisse.compte_comptable
        
        if sens == 'DEBIT':
            # Charge
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte,
                debit=montant,
                credit=0,
                libelle=justification
            )
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_caisse,
                debit=0,
                credit=montant,
                libelle=justification
            )
        else:
            # Produit
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_caisse,
                debit=montant,
                credit=0,
                libelle=justification
            )
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte,
                debit=0,
                credit=montant,
                libelle=justification
            )
        
        # Enregistrer l'écart
        ecart = EcartRapprochement.objects.create(
            releve=releve,
            type_ecart=type_ecart,
            montant=montant,
            sens=sens,
            justification=justification,
            ecriture_correction=ecriture,
            valide=True
        )
        
        return ecart
    
    
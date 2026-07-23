# apps/comptabilite/services/amortissement_service.py
from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction
from django.db.models import Sum
from ..models import Immobilisation, PlanAmortissement, EcritureModel, LigneEcritureModel, JournalModel, ExerciceModel, CompteModel


class AmortissementService:
    """Service de gestion des amortissements"""
    
    @classmethod
    @transaction.atomic
    def generer_plan_amortissement(cls, immobilisation_id):
        """Génère le plan d'amortissement complet"""
        immobilisation = Immobilisation.objects.get(id=immobilisation_id)
        
        # Supprimer ancien plan
        PlanAmortissement.objects.filter(immobilisation=immobilisation).delete()
        
        # Générer le plan
        amortissement_mensuel = immobilisation.amortissement_mensuel
        amortissement_cumule = Decimal('0')
        
        for i in range(immobilisation.duree_ans * 12):
            date_periode = immobilisation.date_acquisition.replace(day=1)
            # Avancer d'un mois
            if date_periode.month == 12:
                date_periode = date_periode.replace(year=date_periode.year + 1, month=1)
            else:
                date_periode = date_periode.replace(month=date_periode.month + 1)
            
            amortissement_cumule += amortissement_mensuel
            valeur_nette = immobilisation.valeur_originale - amortissement_cumule
            
            PlanAmortissement.objects.create(
                immobilisation=immobilisation,
                periode=date_periode,
                montant=amortissement_mensuel,
                amortissement_cumule=amortissement_cumule,
                valeur_nette=valeur_nette,
                ecriture_generee=False
            )
        
        return True
    
    @classmethod
    @transaction.atomic
    def generer_ecriture_amortissement(cls, plan_id, user):
        """Génère l'écriture comptable pour une période d'amortissement"""
        plan = PlanAmortissement.objects.get(id=plan_id)
        
        if plan.ecriture_generee:
            raise ValueError("L'écriture a déjà été générée")
        
        immobilisation = plan.immobilisation
        
        # Récupérer l'exercice
        exercice = ExerciceModel.objects.filter(
            date_debut__lte=plan.periode,
            date_fin__gte=plan.periode,
            cloture=False
        ).first()
        
        if not exercice:
            raise ValueError("Aucun exercice ouvert pour cette période")
        
        # Récupérer le journal OD
        journal, _ = JournalModel.objects.get_or_create(
            code="OD",
            defaults={'libelle': 'Opérations Diverses', 'type_journal': 'OD', 'actif': True}
        )
        
        # Créer l'écriture
        reference = f"AMORT-{immobilisation.code}-{plan.periode.strftime('%Y%m')}"
        
        ecriture = EcritureModel.objects.create(
            reference=reference,
            date_ecriture=plan.periode,
            libelle=f"Amortissement {immobilisation.libelle} - {plan.periode.strftime('%m/%Y')}",
            journal=journal,
            exercice=exercice,
            validee=True,
            created_by=user.username if hasattr(user, 'username') else str(user)
        )
        
        # Ligne débit (Charge d'amortissement)
        LigneEcritureModel.objects.create(
            ecriture=ecriture,
            compte=immobilisation.compte_charge,
            debit=plan.montant,
            credit=0,
            libelle=f"Amortissement {immobilisation.libelle}"
        )
        
        # Ligne crédit (Amortissement cumulé)
        LigneEcritureModel.objects.create(
            ecriture=ecriture,
            compte=immobilisation.compte_amortissement,
            debit=0,
            credit=plan.montant,
            libelle=f"Amortissement {immobilisation.libelle}"
        )
        
        plan.ecriture_generee = True
        plan.ecriture_reference = reference
        plan.save()
        
        return ecriture
    
    @classmethod
    def get_amortissements_mensuels(cls, annee=None, mois=None):
        """Récupère les amortissements pour un mois donné"""
        if not annee:
            annee = date.today().year
        if not mois:
            mois = date.today().month
        
        date_periode = date(annee, mois, 1)
        
        plans = PlanAmortissement.objects.filter(
            periode__year=annee,
            periode__month=mois
        ).select_related('immobilisation')
        
        total = plans.aggregate(total=Sum('montant'))['total'] or 0
        
        return {
            'plans': plans,
            'total': total,
            'periode': date_periode
        }
        
        
        
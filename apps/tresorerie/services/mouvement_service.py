# apps/tresorerie/services/mouvement_service.py
from decimal import Decimal
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from ..models import MouvementCaisse, Caisse


class MouvementService:
    """Service de gestion des mouvements de caisse"""
    
    @staticmethod
    def encaisser(caisse, montant, libelle, user, reference=None, source=None):
        """
        Encaisser un montant dans une caisse
        """
        return MouvementService._creer_mouvement(
            caisse=caisse,
            type_mouvement='ENTREE',
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source
        )
    
    @staticmethod
    def decaisser(caisse, montant, libelle, user, reference=None, source=None):
        """
        Décaisser un montant d'une caisse
        """
        return MouvementService._creer_mouvement(
            caisse=caisse,
            type_mouvement='SORTIE',
            montant=montant,
            libelle=libelle,
            user=user,
            reference=reference,
            source=source
        )
    
    @staticmethod
    @transaction.atomic
    def _creer_mouvement(caisse, type_mouvement, montant, libelle, user, reference=None, source=None):
        """
        Créer un mouvement de caisse et mettre à jour le solde
        """
        montant = Decimal(str(montant))
        
        # Vérifier le solde pour les sorties
        if type_mouvement == 'SORTIE' and caisse.solde < montant:
            raise ValueError(f"Solde insuffisant dans la caisse {caisse.nom}. Solde: {caisse.solde}, Montant: {montant}")
        
        # Détecter le premier mouvement (solde initial)
        est_premier = not MouvementCaisse.objects.filter(caisse=caisse).exists()
        if est_premier and type_mouvement == 'ENTREE':
            libelle = f"[SOLDE INITIAL] {libelle}"
        
        # Créer le mouvement
        mouvement = MouvementCaisse.objects.create(
            caisse=caisse,
            type_mouvement=type_mouvement,
            montant=montant,
            libelle=libelle,
            reference=reference,
            created_by=user,
            date=timezone.now()
        )
        
        # Lier à l'objet source si fourni
        if source:
            content_type = ContentType.objects.get_for_model(source)
            mouvement.content_type = content_type
            mouvement.object_id = source.pk
            mouvement.save()
        
        # Mettre à jour le solde
        if type_mouvement == 'ENTREE':
            caisse.solde += montant
        else:
            caisse.solde -= montant
        caisse.save()

        # Créer l'écriture comptable pour les mouvements significatifs
        if montant > 0:
            try:
                from apps.comptabilite.services.ecriture_comptable import EcritureComptableService
                if '[DEPOT_BANQUE]' in libelle:
                    EcritureComptableService.creer_ecriture_depot_banque(
                        caisse=caisse, montant=montant, libelle=libelle, user=user
                    )
                elif '[RETRAIT_BANQUE]' in libelle:
                    EcritureComptableService.creer_ecriture_retrait_banque(
                        caisse=caisse, montant=montant, libelle=libelle, user=user
                    )
                elif '[APPORT]' in libelle:
                    EcritureComptableService.creer_ecriture_charge(
                        caisse=caisse, montant=montant,
                        libelle=libelle, compte_charge='101', user=user
                    )
                elif '[FINANCEMENT]' in libelle:
                    EcritureComptableService.creer_ecriture_charge(
                        caisse=caisse, montant=montant,
                        libelle=libelle, compte_charge='758', user=user
                    )
                elif '[SOLDE INITIAL]' in libelle:
                    EcritureComptableService.creer_ecriture_charge(
                        caisse=caisse, montant=montant,
                        libelle=libelle, compte_charge='109', user=user
                    )
                elif '[TRANSFERT]' in libelle:
                    if type_mouvement == 'SORTIE':
                        EcritureComptableService.creer_ecriture_transfert(
                            caisse_source=caisse, caisse_dest=None,
                            montant=montant, libelle=libelle, user=user
                        )
                else:
                    journal = EcritureComptableService._determiner_journal_paiement(caisse)
                    if type_mouvement == 'ENTREE':
                        EcritureComptableService.creer_ecriture_charge(
                            caisse=caisse, montant=montant,
                            libelle=libelle, compte_charge='758', user=user
                        )
                    else:
                        EcritureComptableService.creer_ecriture_charge(
                            caisse=caisse, montant=montant,
                            libelle=libelle, compte_charge='658', user=user
                        )
            except Exception as exc:
                from apps.core.models import IntegrationError
                try:
                    IntegrationError.objects.create(
                        module='TRESORERIE',
                        operation='COMPTABILISATION',
                        message=f"Erreur comptable mouvement #{mouvement.id}: {exc}",
                        details=str(exc),
                        traceback=__import__('traceback', fromlist=['format_exc']).format_exc(),
                        status='OPEN',
                    )
                except Exception:
                    pass  # Dernier filet : ne pas planter le mouvement
        
        return mouvement
    
    @staticmethod
    def annuler_mouvement(mouvement, user, raison=""):
        """
        Annuler un mouvement (créer un mouvement inverse)
        """
        if mouvement.type_mouvement == 'ENTREE':
            nouveau_type = 'SORTIE'
        else:
            nouveau_type = 'ENTREE'
        
        annulation = MouvementService._creer_mouvement(
            caisse=mouvement.caisse,
            type_mouvement=nouveau_type,
            montant=mouvement.montant,
            libelle=f"ANNULATION - {mouvement.libelle} - {raison}",
            user=user,
            reference=mouvement.reference
        )
        
        return annulation
    
    
    
    
    
    
    
    
    
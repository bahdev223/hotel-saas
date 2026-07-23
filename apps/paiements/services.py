# apps/paiements/services.py
from decimal import Decimal
from django.db import transaction
from django.contrib.contenttypes.models import ContentType
import uuid
from .models import Paiement
from apps.tresorerie.services import MouvementService
from apps.comptabilite.services import EcritureComptableService


class PaiementService:

    @staticmethod
    @transaction.atomic
    def payer(objet, montant, mode, caisse, user, notes="", reference_externe=""):
        """
        Paiement centralisé
        - objet: instance de n'importe quel modèle (facture, séjour, commande)
        - montant: Decimal
        - mode: ESPECES, CARTE, etc.
        - caisse: instance de Caisse
        - user: utilisateur qui encaisse
        """
        if montant <= 0:
            raise ValueError("Le montant doit être positif")
        
        # Vérifier le reste à payer
        if hasattr(objet, 'reste_a_payer') and montant > objet.reste_a_payer:
            raise ValueError(f"Montant dépasse le reste à payer ({objet.reste_a_payer:,.0f} F)")

        reference = f"PAY-{uuid.uuid4().hex[:8].upper()}"
        
        # 1. Créer le paiement
        paiement = Paiement.objects.create(
            reference=reference,
            montant=montant,
            mode=mode,
            caisse=caisse,
            content_type=ContentType.objects.get_for_model(objet),
            object_id=objet.id,
            created_by=user,
            notes=notes,
            reference_externe=reference_externe,
            statut='VALIDE'
        )
        
        # 2. Mettre à jour la trésorerie (SEULEMENT argent)
        MouvementService.encaisser(
            caisse=caisse,
            montant=montant,
            libelle=f"Paiement {reference}",
            user=user,
            reference=reference
        )
        
        # 3. Mettre à jour le montant payé de l'objet
        if hasattr(objet, 'montant_paye'):
            objet.montant_paye += montant
            objet.save()
        
        # 4. Écriture comptable (séparée)
        EcritureComptableService.enregistrer_paiement(
            montant=montant,
            mode=mode,
            caisse=caisse,
            objet=objet,
            reference=reference,
            user=user
        )
        
        return paiement
    
    
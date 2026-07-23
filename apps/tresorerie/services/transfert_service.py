# apps/tresorerie/services/transfert_service.py
from django.db import transaction
from ..models import TransfertCaisse
from .mouvement_service import MouvementService


class TransfertService:

    @staticmethod
    @transaction.atomic
    def transferer(source, destination, montant, user, notes=""):
        if source.solde < montant:
            raise ValueError(f"Solde insuffisant dans {source.nom}")
        if source == destination:
            raise ValueError("Impossible de transférer vers la même caisse")

        reference = f"TR-{source.id}-{destination.id}-{int(montant)}"

        # Sortie source
        MouvementService.decaisser(
            caisse=source,
            montant=montant,
            libelle=f"[TRANSFERT] Transfert vers {destination.nom}",
            user=user,
            reference=reference
        )

        # Entrée destination
        MouvementService.encaisser(
            caisse=destination,
            montant=montant,
            libelle=f"[TRANSFERT] Transfert depuis {source.nom}",
            user=user,
            reference=reference
        )

        # Trace
        TransfertCaisse.objects.create(
            source=source,
            destination=destination,
            montant=montant,
            reference=reference,
            valide_par=user,
            notes=notes
        )

        return True
    
    
# apps/tresorerie/services/cloture_service.py
from datetime import date
from django.db import transaction
from ..models import JournalCaisse, LigneJournalCaisse


class ClotureService:

    @staticmethod
    @transaction.atomic
    def cloturer_journal(caisse, user):
        """Clôture le journal de caisse pour la journée"""
        
        today = date.today()
        
        # Vérifier si déjà clôturé
        if JournalCaisse.objects.filter(caisse=caisse, date_journal=today, cloture=True).exists():
            raise ValueError("Journal déjà clôturé pour aujourd'hui")
        
        # Calculer les totaux
        mouvements = caisse.mouvements.filter(date__date=today)
        total_entrees = sum(m.montant for m in mouvements if m.type_mouvement == 'ENTREE')
        total_sorties = sum(m.montant for m in mouvements if m.type_mouvement == 'SORTIE')
        
        solde_ouverture = caisse.solde - total_entrees + total_sorties
        solde_theorique = solde_ouverture + total_entrees - total_sorties
        solde_reel = caisse.solde
        ecart = solde_reel - solde_theorique
        
        # Créer le journal
        journal = JournalCaisse.objects.create(
            caisse=caisse,
            date_journal=today,
            solde_ouverture=solde_ouverture,
            total_entrees=total_entrees,
            total_sorties=total_sorties,
            solde_theorique=solde_theorique,
            solde_reel=solde_reel,
            ecart=ecart,
            cloture=True
        )
        
        # Créer les lignes du journal
        for mvt in mouvements:
            LigneJournalCaisse.objects.create(
                journal=journal,
                type_operation=mvt.libelle,
                montant=mvt.montant,
                sens=mvt.type_mouvement,
                reference=mvt.reference,
                libelle=mvt.libelle
            )
        
        return journal
    
    
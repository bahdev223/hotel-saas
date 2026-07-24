from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Supprime les données transactionnelles de la démo (Ventes, Sessions, Journées) pour réinitialiser le système'

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.WARNING("Suppression des données de démo..."))
        
        from apps.pos.models import Vente, LigneVente, SessionCaisse, Commande, LigneCommande
        from apps.core.models import JourneeExploitation
        from apps.paiements.models import Paiement
        
        # Supprimer dans l'ordre inverse des dépendances
        LigneVente.objects.all().delete()
        Vente.objects.all().delete()
        LigneCommande.objects.all().delete()
        Commande.objects.all().delete()
        Paiement.objects.all().delete()
        SessionCaisse.objects.all().delete()
        JourneeExploitation.objects.all().delete()
        
        self.stdout.write(self.style.SUCCESS("✅ Données transactionnelles réinitialisées ! Prêt pour une nouvelle démo."))

from django.db import models

class SourceOperationType(models.TextChoices):
    ACHAT = "ACHAT", "Achat"
    VENTE = "VENTE", "Vente"
    PRODUCTION = "PRODUCTION", "Production"
    CONSOMMATION = "CONSOMMATION", "Consommation"
    PERTE = "PERTE", "Perte"
    INVENTAIRE = "INVENTAIRE", "Inventaire"
    TRANSFERT = "TRANSFERT", "Transfert"
    RETOUR = "RETOUR", "Retour"
    ANNULATION = "ANNULATION", "Annulation"
    INITIALISATION = "INITIALISATION", "Initialisation" # Keep for backwards compatibility

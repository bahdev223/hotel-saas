from django.db import models

class TypeMouvement(models.TextChoices):
    ENTREE = "ENTREE", "Entrée"
    SORTIE = "SORTIE", "Sortie"
    TRANSFERT_ENTREE = "TRANSFERT_ENTREE", "Entrée transfert"
    TRANSFERT_SORTIE = "TRANSFERT_SORTIE", "Sortie transfert"
    AJUSTEMENT_POSITIF = "AJUSTEMENT_POSITIF", "Ajustement positif"
    AJUSTEMENT_NEGATIF = "AJUSTEMENT_NEGATIF", "Ajustement négatif"
    INITIALISATION = "INITIALISATION", "Initialisation" # Keep for backwards compatibility

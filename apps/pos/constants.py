from django.db import models


class TypePointVente(models.TextChoices):
    RESTAURATION = "RESTAURATION", "Restauration"
    BAR = "BAR", "Bar"
    BOUTIQUE = "BOUTIQUE", "Boutique"
    RECEPTION = "RECEPTION", "R\u00e9ception"
    ROOM_SERVICE = "ROOM_SERVICE", "Room service"
    AUTRE = "AUTRE", "Autre"


class ModePrelevement(models.TextChoices):
    STRICT = "STRICT", "Entrep\u00f4t unique"
    CASCADE = "CASCADE", "Entrep\u00f4ts par priorit\u00e9"


class RolePOS(models.TextChoices):
    CAISSIER = "CAISSIER", "Caissier"
    SERVEUR = "SERVEUR", "Serveur"
    RESPONSABLE = "RESPONSABLE", "Responsable"
    SUPERVISEUR = "SUPERVISEUR", "Superviseur"
    PREPARATEUR = "PREPARATEUR", "Pr\u00e9parateur"


class StatutSession(models.TextChoices):
    OUVERTE = "OUVERTE", "Ouverte"
    EN_COMPTAGE = "EN_COMPTAGE", "En comptage"
    FERMEE = "FERMEE", "Ferm\u00e9e"
    VALIDEE = "VALIDEE", "Valid\u00e9e"
    ANNULEE = "ANNULEE", "Annul\u00e9e"


class StatutShift(models.TextChoices):
    PLANIFIE = "PLANIFIE", "Planifi\u00e9"
    CONFIRME = "CONFIRME", "Confirm\u00e9"
    EN_COURS = "EN_COURS", "En cours"
    TERMINE = "TERMINE", "Termin\u00e9"
    ANNULE = "ANNULE", "Annul\u00e9"
    ABSENT = "ABSENT", "Absent"

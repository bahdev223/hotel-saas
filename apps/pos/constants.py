from django.db import models


class TypePointVente(models.TextChoices):
    RESTAURATION = "RESTAURATION", "Restaurant"
    BAR = "BAR", "Bar"

    # Valeurs historiques : elles restent lisibles en base mais ne font plus
    # partie du périmètre opérationnel Vente/POS V2.
    BOUTIQUE = "BOUTIQUE", "Hors périmètre POS - Boutique"
    RECEPTION = "RECEPTION", "Hors périmètre POS - Réception"
    ROOM_SERVICE = "ROOM_SERVICE", "Hors périmètre POS - Room service"
    AUTRE = "AUTRE", "Hors périmètre POS - Autre"


POINTS_VENTE_OPERATIONNELS = frozenset({
    TypePointVente.RESTAURATION,
    TypePointVente.BAR,
})


class ModePrelevement(models.TextChoices):
    STRICT = "STRICT", "Entrep\u00f4t unique"
    CASCADE = "CASCADE", "Entrep\u00f4ts par priorit\u00e9"


class RolePOS(models.TextChoices):
    CAISSIER = "CAISSIER", "Caissier"
    SERVEUR = "SERVEUR", "Serveur"
    RESPONSABLE = "RESPONSABLE", "Responsable"
    SUPERVISEUR = "SUPERVISEUR", "Superviseur"
    PREPARATEUR = "PREPARATEUR", "Pr\u00e9parateur"


class ModeAccesPOS(models.TextChoices):
    TOTAL = "TOTAL", "Accès total"
    PERMANENT = "PERMANENT", "Accès permanent"
    HORAIRES = "HORAIRES", "Accès selon horaires"
    PLANNING = "PLANNING", "Accès selon planning"


class ActionPOS:
    ACCEDER = "ACCEDER"
    VENDRE = "VENDRE"
    ENCAISSER = "ENCAISSER"
    OUVRIR_CAISSE = "OUVRIR_CAISSE"
    FERMER_CAISSE = "FERMER_CAISSE"
    ANNULER_VENTE = "ANNULER_VENTE"
    ACCORDER_REMISE = "ACCORDER_REMISE"
    CONSULTER_RAPPORTS = "CONSULTER_RAPPORTS"


ROLE_PERMISSION_PRESETS = {
    RolePOS.CAISSIER: {
        ActionPOS.VENDRE: True,
        ActionPOS.ENCAISSER: True,
        ActionPOS.OUVRIR_CAISSE: True,
        ActionPOS.FERMER_CAISSE: True,
    },
    RolePOS.SERVEUR: {
        ActionPOS.VENDRE: True,
    },
    RolePOS.RESPONSABLE: {
        ActionPOS.VENDRE: True,
        ActionPOS.ENCAISSER: True,
        ActionPOS.OUVRIR_CAISSE: True,
        ActionPOS.FERMER_CAISSE: True,
        ActionPOS.ANNULER_VENTE: True,
        ActionPOS.ACCORDER_REMISE: True,
        ActionPOS.CONSULTER_RAPPORTS: True,
    },
    RolePOS.SUPERVISEUR: {
        ActionPOS.VENDRE: True,
        ActionPOS.ENCAISSER: True,
        ActionPOS.OUVRIR_CAISSE: True,
        ActionPOS.FERMER_CAISSE: True,
        ActionPOS.ANNULER_VENTE: True,
        ActionPOS.ACCORDER_REMISE: True,
        ActionPOS.CONSULTER_RAPPORTS: True,
    },
    RolePOS.PREPARATEUR: {},
}


class StatutSession(models.TextChoices):
    OUVERTE = "OUVERTE", "Ouverte"
    EN_PASSATION = "EN_PASSATION", "En passation"
    EN_COMPTAGE = "EN_COMPTAGE", "En comptage"
    FERMEE = "FERMEE", "Fermée"
    VALIDEE = "VALIDEE", "Validée"
    ANNULEE = "ANNULEE", "Annulée"


class StatutShift(models.TextChoices):
    PLANIFIE = "PLANIFIE", "Planifi\u00e9"
    CONFIRME = "CONFIRME", "Confirm\u00e9"
    EN_COURS = "EN_COURS", "En cours"
    TERMINE = "TERMINE", "Termin\u00e9"
    ANNULE = "ANNULE", "Annul\u00e9"
    ABSENT = "ABSENT", "Absent"

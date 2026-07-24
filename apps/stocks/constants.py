from django.db import models


class TypesArticle(models.TextChoices):
    MATIERE_PREMIERE = "MATIERE_PREMIERE", "MatiÃ¨re premiÃ¨re"
    PRODUIT_FINI = "PRODUIT_FINI", "Produit fini"
    PRODUIT_SEMI_FINI = "PRODUIT_SEMI_FINI", "Produit semi-fini"
    EMBALLAGE = "EMBALLAGE", "Emballage"
    CONSOMMABLE = "CONSOMMABLE", "Consommable"
    FOURNITURE = "FOURNITURE", "Fourniture"
    PIECE_DETACHEE = "PIECE_DETACHEE", "PiÃ¨ce dÃ©tachÃ©e"
    SERVICE_STOCKABLE = "SERVICE_STOCKABLE", "Service stockable"
    AUTRE = "AUTRE", "Autre"


class NatureMouvement(models.TextChoices):
    ENTREE = "ENTREE", "EntrÃ©e"
    SORTIE = "SORTIE", "Sortie"
    TRANSFERT = "TRANSFERT", "Transfert"
    AJUSTEMENT = "AJUSTEMENT", "Ajustement"


class MethodeValorisation(models.TextChoices):
    PMP = "PMP", "Prix Moyen PondÃ©rÃ©"
    FIFO = "FIFO", "Premier entrÃ©, premier sorti"
    DMP = "DMP", "Dernier prix d'achat"
    NONE = "NONE", "Aucune valorisation"


class CategorieUnite(models.TextChoices):
    MASSE = "MASSE", "Masse"
    VOLUME = "VOLUME", "Volume"
    UNITE = "UNITE", "UnitÃ©"
    LONGUEUR = "LONGUEUR", "Longueur"
    SURFACE = "SURFACE", "Surface"
    TEMPS = "TEMPS", "Temps"
    MONNAIE = "MONNAIE", "Monnaie"
    AUTRE = "AUTRE", "Autre"


class FamilleSource(models.TextChoices):
    APPROVISIONNEMENT = "APPROVISIONNEMENT", "Approvisionnement"
    DISTRIBUTION = "DISTRIBUTION", "Distribution"
    PRODUCTION = "PRODUCTION", "Production"
    LOGISTIQUE = "LOGISTIQUE", "Logistique"
    INCIDENTS = "INCIDENTS", "Incidents"
    TECHNIQUE = "TECHNIQUE", "Technique"
    AUTRE = "AUTRE", "Autre"


class StatutInventaire(models.TextChoices):
    BROUILLON = "BROUILLON", "Brouillon"
    EN_COURS = "EN_COURS", "En cours"
    VALIDE = "VALIDE", "ValidÃ©"
    ANNULE = "ANNULE", "AnnulÃ©"


SOURCES_SYSTEME = {
    "ACHAT": {"nom": "Achat", "famille": FamilleSource.APPROVISIONNEMENT},
    "RETOUR_FOURNISSEUR": {"nom": "Retour fournisseur", "famille": FamilleSource.APPROVISIONNEMENT},
    "DON_RECU": {"nom": "Don reÃ§u", "famille": FamilleSource.APPROVISIONNEMENT},
    "IMPORT": {"nom": "Import", "famille": FamilleSource.APPROVISIONNEMENT},
    "INITIALISATION": {"nom": "Initialisation", "famille": FamilleSource.APPROVISIONNEMENT},
    "VENTE": {"nom": "Vente", "famille": FamilleSource.DISTRIBUTION},
    "DON": {"nom": "Don", "famille": FamilleSource.DISTRIBUTION},
    "EXPORT": {"nom": "Export", "famille": FamilleSource.DISTRIBUTION},
    "PRODUCTION": {"nom": "Production", "famille": FamilleSource.PRODUCTION},
    "CONSOMMATION_PRODUCTION": {"nom": "Consommation production", "famille": FamilleSource.PRODUCTION},
    "TRANSFERT": {"nom": "Transfert", "famille": FamilleSource.LOGISTIQUE},
    "INVENTAIRE": {"nom": "Inventaire", "famille": FamilleSource.LOGISTIQUE},
    "AJUSTEMENT": {"nom": "Ajustement", "famille": FamilleSource.LOGISTIQUE},
    "CASSE": {"nom": "Casse", "famille": FamilleSource.INCIDENTS},
    "PEREMPTION": {"nom": "PÃ©remption", "famille": FamilleSource.INCIDENTS},
    "VOL": {"nom": "Vol", "famille": FamilleSource.INCIDENTS},
    "PERTE": {"nom": "Perte", "famille": FamilleSource.INCIDENTS},
    "CORRECTION": {"nom": "Correction", "famille": FamilleSource.TECHNIQUE},
    "AUTRE": {"nom": "Autre", "famille": FamilleSource.AUTRE},
}


COMPORTEMENT_PAR_DEFAUT = {
    "stockable": True,
    "vendable": True,
    "achetable": True,
    "perissable": False,
    "lot_obligatoire": False,
    "numero_serie": False,
    "inventoriable": True,
}

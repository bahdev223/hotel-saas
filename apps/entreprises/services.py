from django.db import transaction
from django.utils import timezone

from .models import (
    Entreprise,
    Etablissement,
    ConfigurationEntreprise,
    ConfigurationHoteliere,
    ModuleEntreprise,
    SequenceDocument,
)


@transaction.atomic
def creer_installation_complete(
    *,
    nom_entreprise,
    code_entreprise,
    nom_etablissement,
    code_etablissement,
    type_etablissement=Etablissement.TypeEtablissement.HOTEL,
    **kwargs,
):
    entreprise = Entreprise.objects.create(
        nom=nom_entreprise,
        code=code_entreprise,
        **{k: v for k, v in kwargs.items() if hasattr(Entreprise, k)},
    )

    etablissement = Etablissement.objects.create(
        entreprise=entreprise,
        nom=nom_etablissement,
        code=code_etablissement,
        type_etablissement=type_etablissement,
    )

    ConfigurationEntreprise.objects.create(entreprise=entreprise)
    ConfigurationHoteliere.objects.create(etablissement=etablissement)

    for code, _ in ModuleEntreprise.CodeModule.choices:
        ModuleEntreprise.objects.create(
            entreprise=entreprise,
            code=code,
            actif=True,
        )

    annee = timezone.now().year
    sequences = [
        ("RESERVATION", "RES"),
        ("SEJOUR", "SEJ"),
        ("FACTURE", "FAC"),
        ("RECU", "REC"),
        ("AVOIR", "AVR"),
        ("COMMANDE", "CMD"),
        ("ACHAT", "ACH"),
        ("INVENTAIRE", "INV"),
        ("BON_LIVRAISON", "BL"),
        ("DEPENSE", "DEP"),
        ("TRANSFERT", "TRF"),
    ]
    for type_doc, prefixe in sequences:
        SequenceDocument.objects.create(
            entreprise=entreprise,
            type_document=type_doc,
            prefixe=prefixe,
            annee=annee,
        )

    return entreprise, etablissement


def obtenir_entreprise_actuelle():
    return Entreprise.objects.filter(actif=True).first()


def obtenir_etablissement_actuel():
    entreprise = obtenir_entreprise_actuelle()
    if entreprise:
        return entreprise.etablissements.filter(actif=True).first()
    return None

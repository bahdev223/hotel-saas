from .models import (
    Entreprise,
    Etablissement,
    ConfigurationEntreprise,
    ConfigurationHoteliere,
    ModuleEntreprise,
    SequenceDocument,
)


def liste_entreprises(actif=True):
    qs = Entreprise.objects.all()
    if actif is not None:
        qs = qs.filter(actif=actif)
    return qs


def liste_etablissements(entreprise=None, actif=True):
    qs = Etablissement.objects.select_related("entreprise").all()
    if entreprise:
        qs = qs.filter(entreprise=entreprise)
    if actif is not None:
        qs = qs.filter(actif=actif)
    return qs


def configuration_entreprise(entreprise):
    return ConfigurationEntreprise.objects.filter(entreprise=entreprise).first()


def configuration_hoteliere(etablissement):
    return ConfigurationHoteliere.objects.filter(etablissement=etablissement).first()


def modules_actifs(entreprise):
    return ModuleEntreprise.objects.filter(
        entreprise=entreprise,
        actif=True,
    ).values_list("code", flat=True)


def prochaine_sequence(entreprise, type_document, annee=None):
    from django.utils import timezone
    if annee is None:
        annee = timezone.now().year
    return SequenceDocument.objects.filter(
        entreprise=entreprise,
        type_document=type_document,
        annee=annee,
    ).first()

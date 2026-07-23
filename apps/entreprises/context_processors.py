from .models import Entreprise


def entreprise_context(request):
    entreprise = Entreprise.objects.filter(actif=True).first()
    etablissement = (
        entreprise.etablissements.filter(actif=True).first()
        if entreprise
        else None
    )

    config = getattr(entreprise, "configuration", None) if entreprise else None

    return {
        "entreprise_courante": entreprise,
        "etablissement_courant": etablissement,
        "configuration_entreprise": config,
    }

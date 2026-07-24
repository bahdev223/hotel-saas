from .models import Entreprise


class _EntreprisePlaceholder:
    """Remplace None pour les templates qui accèdent à entreprise_courante.*"""
    nom = ''
    nom_commercial = ''
    logo = None
    def __bool__(self):
        return False


def entreprise_context(request):
    entreprise = Entreprise.objects.filter(actif=True).first()
    if entreprise is None:
        entreprise = _EntreprisePlaceholder()
    etablissement = (
        entreprise.etablissements.filter(actif=True).first()
        if hasattr(entreprise, 'etablissements') and entreprise
        else None
    )

    config = getattr(entreprise, "configuration", None) if entreprise and hasattr(entreprise, 'configuration') else None

    return {
        "entreprise_courante": entreprise,
        "etablissement_courant": etablissement,
        "configuration_entreprise": config,
    }

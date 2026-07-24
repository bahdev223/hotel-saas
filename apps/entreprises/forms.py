from django import forms

from .models import (
    Entreprise,
    Etablissement,
    ConfigurationEntreprise,
    ConfigurationHoteliere,
    ModuleEntreprise,
)


class EntrepriseForm(forms.ModelForm):
    class Meta:
        model = Entreprise
        fields = [
            "nom",
            "nom_commercial",
            "code",
            "forme_juridique",
            "nif",
            "rccm",
            "numero_statistique",
            "numero_art",
            "telephone",
            "telephone_secondaire",
            "email",
            "site_web",
            "adresse",
            "ville",
            "pays",
            "logo",
            "cachet",
            "signature",
        ]


class EtablissementForm(forms.ModelForm):
    class Meta:
        model = Etablissement
        fields = [
            "entreprise",
            "nom",
            "code",
            "type_etablissement",
            "telephone",
            "email",
            "adresse",
            "ville",
            "nombre_etoiles",
        ]


class ConfigurationEntrepriseForm(forms.ModelForm):
    class Meta:
        model = ConfigurationEntreprise
        fields = [
            "devise",
            "symbole_devise",
            "langue",
            "fuseau_horaire",
            "format_date",
            "exercice_comptable_debut_mois",
            "couleur_principale",
            "couleur_secondaire",
            "pied_facture",
            "conditions_facture",
        ]


class ConfigurationHoteliereForm(forms.ModelForm):
    class Meta:
        model = ConfigurationHoteliere
        fields = [
            "heure_check_in",
            "heure_check_out",
            "autoriser_arrivee_anticipee",
            "autoriser_depart_tardif",
            "pourcentage_acompte_reservation",
            "delai_annulation_gratuite_heures",
            "liberation_automatique_chambre",
            "passage_nettoyage_apres_depart",
            "autoriser_surclassement",
            "autoriser_changement_chambre",
            "texte_confirmation_reservation",
            "politique_annulation",
        ]


class ModuleEntrepriseForm(forms.ModelForm):
    class Meta:
        model = ModuleEntreprise
        fields = ["code", "actif"]

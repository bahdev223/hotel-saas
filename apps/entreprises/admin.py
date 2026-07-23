from unfold.admin import ModelAdmin
from django.contrib import admin

from .models import (
    Entreprise,
    Etablissement,
    ConfigurationEntreprise,
    ConfigurationHoteliere,
    ModuleEntreprise,
    SequenceDocument,
)


@admin.register(Entreprise)
class EntrepriseAdmin(ModelAdmin):
    list_display = ["nom", "nom_commercial", "code", "nif", "telephone", "actif"]
    list_filter = ["forme_juridique", "actif", "pays"]
    search_fields = ["nom", "nom_commercial", "code", "nif", "rccm"]
    readonly_fields = ["cree_le", "modifie_le"]


@admin.register(Etablissement)
class EtablissementAdmin(ModelAdmin):
    list_display = ["nom", "code", "entreprise", "type_etablissement", "ville", "actif"]
    list_filter = ["type_etablissement", "actif", "ville"]
    search_fields = ["nom", "code", "entreprise__nom"]
    autocomplete_fields = ["entreprise"]
    readonly_fields = ["cree_le", "modifie_le"]


@admin.register(ConfigurationEntreprise)
class ConfigurationEntrepriseAdmin(ModelAdmin):
    list_display = ["entreprise", "devise", "symbole_devise", "langue", "configuration_terminee"]
    list_filter = ["langue", "configuration_terminee"]
    search_fields = ["entreprise__nom"]
    autocomplete_fields = ["entreprise"]


@admin.register(ConfigurationHoteliere)
class ConfigurationHoteliereAdmin(ModelAdmin):
    list_display = ["etablissement", "heure_check_in", "heure_check_out"]
    search_fields = ["etablissement__nom"]
    autocomplete_fields = ["etablissement"]


@admin.register(ModuleEntreprise)
class ModuleEntrepriseAdmin(ModelAdmin):
    list_display = ["entreprise", "code", "actif"]
    list_filter = ["code", "actif"]
    search_fields = ["entreprise__nom"]
    autocomplete_fields = ["entreprise"]


@admin.register(SequenceDocument)
class SequenceDocumentAdmin(ModelAdmin):
    list_display = ["entreprise", "type_document", "prefixe", "prochain_numero", "annee"]
    list_filter = ["type_document", "annee"]
    search_fields = ["entreprise__nom", "prefixe"]
    autocomplete_fields = ["entreprise"]

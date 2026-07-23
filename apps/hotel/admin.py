from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import UniteModel, LocationModel


@admin.register(UniteModel)
class UniteModelAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_unite', 'capacite', 'prix', 'statut', 'actif']
    list_filter = ['type_unite', 'statut', 'actif']
    search_fields = ['code', 'nom']
    list_editable = ['statut', 'actif']


@admin.register(LocationModel)
class LocationModelAdmin(ModelAdmin):
    list_display = ['id', 'client', 'unite', 'type_location', 'date_debut', 'date_fin', 'montant_total', 'statut']
    list_filter = ['type_location', 'statut', 'date_debut']
    search_fields = ['id', 'client__nom', 'client__prenom', 'unite__code']
    autocomplete_fields = ['client', 'unite']
    readonly_fields = ['created_at', 'updated_at']

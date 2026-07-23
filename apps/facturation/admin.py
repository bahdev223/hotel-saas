from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import FactureModel, LigneFactureModel


class LigneFactureInline(TabularInline):
    model = LigneFactureModel
    extra = 1
    fields = ['description', 'quantite', 'prix_unitaire', 'tva']


@admin.register(FactureModel)
class FactureAdmin(ModelAdmin):
    list_display = ['numero', 'client_nom', 'date_emission', 'montant_total', 'statut']
    list_filter = ['statut', 'date_emission']
    search_fields = ['numero', 'client_nom']
    inlines = [LigneFactureInline]
    readonly_fields = ['date_emission', 'created_at']

    def montant_total(self, obj):
        return obj.montant_total
    montant_total.short_description = 'Total'


@admin.register(LigneFactureModel)
class LigneFactureAdmin(ModelAdmin):
    list_display = ['facture', 'description', 'quantite', 'prix_unitaire', 'tva']
    search_fields = ['description', 'facture__numero']
    autocomplete_fields = ['facture']

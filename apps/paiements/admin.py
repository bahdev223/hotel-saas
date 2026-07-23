from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import Paiement


@admin.register(Paiement)
class PaiementAdmin(ModelAdmin):
    list_display = ['reference', 'type_paiement', 'montant', 'sens', 'mode', 'caisse', 'date', 'statut']
    list_filter = ['type_paiement', 'mode', 'sens', 'statut', 'date']
    search_fields = ['reference', 'reference_externe', 'notes']
    autocomplete_fields = ['caisse', 'created_by', 'valide_par']
    readonly_fields = ['date', 'created_at', 'updated_at']


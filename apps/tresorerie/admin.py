from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import Caisse, MouvementCaisse, TransfertCaisse, JournalCaisse, LigneJournalCaisse


class MouvementInline(TabularInline):
    model = MouvementCaisse
    extra = 0
    fields = ['type_mouvement', 'montant', 'libelle', 'date']
    readonly_fields = ['date']


class LigneJournalInline(TabularInline):
    model = LigneJournalCaisse
    extra = 1
    fields = ['type_operation', 'montant', 'sens', 'libelle']


@admin.register(Caisse)
class CaisseAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_financier', 'role', 'solde', 'actif']
    list_filter = ['type_financier', 'role', 'actif']
    search_fields = ['code', 'nom']
    autocomplete_fields = ['compte_comptable']


@admin.register(MouvementCaisse)
class MouvementCaisseAdmin(ModelAdmin):
    list_display = ['caisse', 'type_mouvement', 'montant', 'libelle', 'date', 'created_by', 'annule']
    list_filter = ['type_mouvement', 'annule', 'date']
    search_fields = ['libelle', 'reference']
    autocomplete_fields = ['caisse', 'created_by', 'annule_par']
    inlines = [MouvementInline]


@admin.register(TransfertCaisse)
class TransfertCaisseAdmin(ModelAdmin):
    list_display = ['source', 'destination', 'montant', 'reference', 'date', 'valide_par']
    search_fields = ['reference']
    autocomplete_fields = ['source', 'destination', 'valide_par']
    readonly_fields = ['date']


@admin.register(JournalCaisse)
class JournalCaisseAdmin(ModelAdmin):
    list_display = ['caisse', 'date_journal', 'solde_ouverture', 'total_entrees', 'total_sorties', 'solde_theorique', 'solde_reel', 'ecart', 'cloture']
    list_filter = ['cloture', 'date_journal']
    search_fields = ['caisse__nom']
    autocomplete_fields = ['caisse']
    inlines = [LigneJournalInline]
    readonly_fields = ['date_journal', 'solde_ouverture', 'total_entrees', 'total_sorties', 'solde_theorique', 'solde_reel', 'ecart']


@admin.register(LigneJournalCaisse)
class LigneJournalCaisseAdmin(ModelAdmin):
    list_display = ['journal', 'type_operation', 'montant', 'sens', 'libelle']
    autocomplete_fields = ['journal']


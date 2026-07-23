from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import PeriodePaie, RubriquePaie, BulletinPaie, LigneBulletinPaie, AvanceSalaire, LigneRemboursement


class LigneBulletinInline(TabularInline):
    model = LigneBulletinPaie
    extra = 1
    fields = ['rubrique', 'base', 'taux', 'montant', 'ordre']


class LigneRemboursementInline(TabularInline):
    model = LigneRemboursement
    extra = 0
    fields = ['mois', 'annee', 'montant', 'rembourse']


@admin.register(PeriodePaie)
class PeriodePaieAdmin(ModelAdmin):
    list_display = ['annee', 'mois', 'date_debut', 'date_fin', 'cloture', 'date_cloture']
    list_filter = ['cloture', 'annee', 'mois']
    search_fields = ['annee', 'mois']


@admin.register(RubriquePaie)
class RubriquePaieAdmin(ModelAdmin):
    list_display = ['code', 'libelle', 'type_rubrique', 'sens', 'taux', 'montant_fixe', 'actif', 'ordre']
    list_filter = ['type_rubrique', 'sens', 'actif']
    search_fields = ['code', 'libelle']
    list_editable = ['actif', 'ordre']


@admin.register(BulletinPaie)
class BulletinPaieAdmin(ModelAdmin):
    list_display = ['numero', 'employe', 'periode', 'total_brut', 'net_a_payer', 'statut', 'date_calcul']
    list_filter = ['statut', 'periode']
    search_fields = ['numero', 'employe__matricule', 'employe__nom']
    autocomplete_fields = ['employe', 'periode', 'contrat']
    inlines = [LigneBulletinInline]
    readonly_fields = ['date_calcul', 'total_brut', 'total_cotisations', 'total_impots', 'net_a_payer']


@admin.register(AvanceSalaire)
class AvanceSalaireAdmin(ModelAdmin):
    list_display = ['id', 'employe', 'montant', 'date_demande', 'statut', 'mois_remboursement', 'annee_remboursement']
    list_filter = ['statut']
    search_fields = ['id', 'employe__matricule', 'employe__nom']
    autocomplete_fields = ['employe']
    inlines = [LigneRemboursementInline]


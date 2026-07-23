# apps/comptabilite/admin.py
from django.contrib import admin
from django.utils.html import format_html
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    ExerciceModel, CompteModel, TiersModel, JournalModel,
    EcritureModel, LigneEcritureModel, CompteTiersModel,
    Immobilisation, PlanAmortissement,
    ConfigurationEntreprise, SoldesInitiaux, ParametreEntreprise,
    ReleveBancaire, LigneReleveBancaire, EcartRapprochement,
)


class LigneEcritureInline(TabularInline):
    """Lignes d'écriture dans l'admin"""
    model = LigneEcritureModel
    extra = 2
    fields = ['compte', 'debit', 'credit', 'libelle', 'tiers']
    autocomplete_fields = ['compte', 'tiers']


@admin.register(ExerciceModel)
class ExerciceAdmin(ModelAdmin):
    list_display = ['code', 'date_debut', 'date_fin', 'display_statut', 'date_cloture']
    list_filter = ['cloture']
    search_fields = ['code']
    
    def display_statut(self, obj):
        if obj.cloture:
            return format_html('<span class="bg-red-100 text-red-800 px-2 py-1 rounded">Cloture</span>')
        return format_html('<span class="bg-green-100 text-green-800 px-2 py-1 rounded">Ouvert</span>')
    display_statut.short_description = 'Statut'
    
    actions = ['cloturer_exercice', 'rouvrir_exercice']
    
    def cloturer_exercice(self, request, queryset):
        from datetime import date
        for exercice in queryset:
            if not exercice.cloture:
                exercice.cloture = True
                exercice.date_cloture = date.today()
                exercice.save()
        self.message_user(request, f'{queryset.count()} exercice(s) cloture(s)')
    cloturer_exercice.short_description = 'Cloturer les exercices selectionnes'
    
    def rouvrir_exercice(self, request, queryset):
        for exercice in queryset:
            if exercice.cloture:
                exercice.cloture = False
                exercice.date_cloture = None
                exercice.save()
        self.message_user(request, f'{queryset.count()} exercice(s) rouvert(s)')
    rouvrir_exercice.short_description = 'Rouvrir les exercices selectionnes'


@admin.register(CompteModel)
class CompteAdmin(ModelAdmin):
    list_display = ['code', 'libelle_court', 'display_nature', 'niveau', 'type_compte', 'est_mouvement', 'display_categorie']
    list_filter = ['nature', 'type_compte', 'est_mouvement', 'categorie', 'niveau']
    search_fields = ['code', 'libelle']
    list_per_page = 50
    autocomplete_fields = ['parent']
    
    fieldsets = (
        ('Identification', {
            'fields': ('code', 'libelle'),
            'classes': ['tab']
        }),
        ('Classification SYSCOHADA', {
            'fields': ('nature', 'sens', 'categorie', 'type_compte'),
            'classes': ['tab']
        }),
        ('Hierarchie', {
            'fields': ('parent', 'niveau'),
            'classes': ['tab']
        }),
        ('Options', {
            'fields': ('est_mouvement', 'actif'),
            'classes': ['tab']
        }),
    )
    
    def libelle_court(self, obj):
        if len(obj.libelle) > 60:
            return obj.libelle[:60] + '...'
        return obj.libelle
    libelle_court.short_description = 'Libelle'
    
    def display_nature(self, obj):
        colors = {
            'ACTIF': 'bg-green-100 text-green-800',
            'PASSIF': 'bg-red-100 text-red-800',
            'CHARGE': 'bg-orange-100 text-orange-800',
            'PRODUIT': 'bg-blue-100 text-blue-800',
            'MIXTE': 'bg-purple-100 text-purple-800',
            'NEUTRE': 'bg-gray-100 text-gray-800',
        }
        color = colors.get(obj.nature, 'bg-gray-100 text-gray-800')
        return format_html(f'<span class="px-2 py-1 rounded text-xs {color}">{obj.nature}</span>')
    display_nature.short_description = 'Nature'
    
    def display_categorie(self, obj):
        if obj.categorie == 'bilan':
            return format_html('<span class="bg-blue-100 text-blue-800 px-2 py-1 rounded text-xs">Bilan</span>')
        return format_html('<span class="bg-green-100 text-green-800 px-2 py-1 rounded text-xs">Resultat</span>')
    display_categorie.short_description = 'Categorie'
    
    actions = ['activer_comptes', 'desactiver_comptes']
    
    def activer_comptes(self, request, queryset):
        updated = queryset.update(actif=True)
        self.message_user(request, f'{updated} compte(s) active(s)')
    activer_comptes.short_description = 'Activer les comptes selectionnes'
    
    def desactiver_comptes(self, request, queryset):
        updated = queryset.update(actif=False)
        self.message_user(request, f'{updated} compte(s) desactive(s)')
    desactiver_comptes.short_description = 'Desactiver les comptes selectionnes'


@admin.register(TiersModel)
class TiersAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_tiers', 'compte', 'telephone', 'actif']
    list_filter = ['type_tiers', 'actif']
    search_fields = ['code', 'nom', 'telephone', 'email']
    autocomplete_fields = ['compte']


@admin.register(JournalModel)
class JournalAdmin(ModelAdmin):
    list_display = ['code', 'libelle', 'type_journal', 'actif']
    list_filter = ['type_journal', 'actif']
    search_fields = ['code', 'libelle']


@admin.register(EcritureModel)
class EcritureAdmin(ModelAdmin):
    list_display = ['reference', 'date_ecriture', 'journal', 'libelle_court', 'total_debit', 'total_credit', 'display_equilibre', 'validee']
    list_filter = ['journal', 'validee', 'date_ecriture', 'exercice']
    search_fields = ['reference', 'libelle', 'piece']
    autocomplete_fields = ['journal', 'exercice']
    inlines = [LigneEcritureInline]
    readonly_fields = ['created_at', 'total_debit', 'total_credit']
    
    fieldsets = (
        ('Identification', {
            'fields': ('reference', 'date_ecriture', 'exercice', 'journal')
        }),
        ('Contenu', {
            'fields': ('libelle', 'piece')
        }),
        ('Validation', {
            'fields': ('validee', 'date_validation', 'created_by')
        }),
        ('Totaux', {
            'fields': ('total_debit', 'total_credit'),
            'classes': ('collapse',)
        }),
    )
    
    def libelle_court(self, obj):
        if len(obj.libelle) > 50:
            return obj.libelle[:50] + '...'
        return obj.libelle
    libelle_court.short_description = 'Libelle'
    
    def display_equilibre(self, obj):
        if obj.est_equilibree:
            return format_html('<span class="bg-green-100 text-green-800 px-2 py-1 rounded">Equilibree</span>')
        return format_html('<span class="bg-red-100 text-red-800 px-2 py-1 rounded">Desequilibree</span>')
    display_equilibre.short_description = 'Equilibre'
    
    def save_model(self, request, obj, form, change):
        if not obj.created_by:
            obj.created_by = request.user.username
        super().save_model(request, obj, form, change)
    
    actions = ['valider_ecritures', 'invalider_ecritures']
    
    def valider_ecritures(self, request, queryset):
        from datetime import datetime
        for ecriture in queryset:
            if not ecriture.validee and ecriture.est_equilibree:
                ecriture.validee = True
                ecriture.date_validation = datetime.now()
                ecriture.save()
        self.message_user(request, f'{queryset.count()} ecriture(s) validee(s)')
    valider_ecritures.short_description = 'Valider les ecritures selectionnees'
    
    def invalider_ecritures(self, request, queryset):
        for ecriture in queryset:
            if ecriture.validee:
                ecriture.validee = False
                ecriture.date_validation = None
                ecriture.save()
        self.message_user(request, f'{queryset.count()} ecriture(s) invalidee(s)')
    invalider_ecritures.short_description = 'Invalider les ecritures selectionnees'


@admin.register(CompteTiersModel)
class CompteTiersAdmin(ModelAdmin):
    list_display = ['tiers', 'exercice', 'solde', 'ecart_lettrage']
    list_filter = ['exercice']
    search_fields = ['tiers__code', 'tiers__nom']
    autocomplete_fields = ['tiers', 'exercice']


# ========== MODÈLES AJOUTÉS ==========

class PlanAmortissementInline(TabularInline):
    model = PlanAmortissement
    extra = 1
    fields = ['periode', 'montant', 'amortissement_cumule', 'valeur_nette', 'ecriture_generee']
    readonly_fields = ['amortissement_cumule', 'valeur_nette']


@admin.register(Immobilisation)
class ImmobilisationAdmin(ModelAdmin):
    list_display = ['code', 'libelle', 'type_immobilisation', 'date_acquisition', 'valeur_originale', 'statut']
    list_filter = ['type_immobilisation', 'statut']
    search_fields = ['code', 'libelle']
    autocomplete_fields = ['compte_immobilisation', 'compte_amortissement', 'compte_charge']
    inlines = [PlanAmortissementInline]


@admin.register(PlanAmortissement)
class PlanAmortissementAdmin(ModelAdmin):
    list_display = ['immobilisation', 'periode', 'montant', 'amortissement_cumule', 'valeur_nette', 'ecriture_generee']
    list_filter = ['ecriture_generee']
    autocomplete_fields = ['immobilisation']


@admin.register(ConfigurationEntreprise)
class ConfigurationEntrepriseAdmin(ModelAdmin):
    list_display = ['nom', 'devise', 'nif', 'stat', 'rccm', 'est_initialise']
    search_fields = ['nom', 'nif']
    autocomplete_fields = ['exercice']


@admin.register(SoldesInitiaux)
class SoldesInitiauxAdmin(ModelAdmin):
    list_display = ['configuration', 'caisse', 'banque', 'stocks', 'clients', 'fournisseurs', 'capital_social']
    autocomplete_fields = ['configuration']


@admin.register(ParametreEntreprise)
class ParametreEntrepriseAdmin(ModelAdmin):
    list_display = ['entreprise', 'mode_paie', 'gerer_cnps', 'gerer_impots', 'gerer_tva', 'taux_tva']
    autocomplete_fields = ['entreprise']


class LigneReleveInline(TabularInline):
    model = LigneReleveBancaire
    extra = 1
    fields = ['date_operation', 'libelle', 'montant', 'sens', 'statut']


class EcartRapprochementInline(TabularInline):
    model = EcartRapprochement
    extra = 0
    fields = ['type_ecart', 'montant', 'sens', 'justification', 'valide']


@admin.register(ReleveBancaire)
class ReleveBancaireAdmin(ModelAdmin):
    list_display = ['caisse', 'date_debut', 'date_fin', 'solde_ouverture', 'solde_cloture', 'statut']
    list_filter = ['statut']
    search_fields = ['caisse__nom']
    autocomplete_fields = ['caisse', 'created_by']
    inlines = [LigneReleveInline, EcartRapprochementInline]


@admin.register(LigneReleveBancaire)
class LigneReleveBancaireAdmin(ModelAdmin):
    list_display = ['releve', 'date_operation', 'libelle', 'montant', 'sens', 'statut']
    list_filter = ['statut', 'sens']
    autocomplete_fields = ['releve', 'ecriture_rapprochee']


@admin.register(EcartRapprochement)
class EcartRapprochementAdmin(ModelAdmin):
    list_display = ['releve', 'type_ecart', 'montant', 'sens', 'valide']
    list_filter = ['type_ecart', 'valide']
    autocomplete_fields = ['releve', 'ecriture_correction']
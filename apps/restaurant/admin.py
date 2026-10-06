from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline, StackedInline

from .models import FileAttenteModel, SalleModel, TableModel, RecetteModel, IngredientModel, EtapePreparationModel, MenuModel, LigneMenuModel, Production, ProductionLigne, ProductionIngredient


class IngredientInline(TabularInline):
    model = IngredientModel
    extra = 1
    fields = ['produit', 'type_ingredient', 'quantite', 'unite']


class EtapeInline(TabularInline):
    model = EtapePreparationModel
    extra = 1
    fields = ['ordre', 'instruction', 'duree_minutes']


class LigneMenuInline(TabularInline):
    model = LigneMenuModel
    extra = 1
    fields = ['recette', 'groupe', 'type_ligne', 'quantite', 'prix_supplement']


class ProductionLigneInline(TabularInline):
    model = ProductionLigne
    extra = 1
    fields = ['menu', 'quantite']


class ProductionIngredientInline(TabularInline):
    model = ProductionIngredient
    extra = 0
    fields = ['produit', 'quantite', 'unite']
    readonly_fields = ['produit', 'quantite', 'unite']


@admin.register(FileAttenteModel)
class FileAttenteAdmin(ModelAdmin):
    list_display = [
        'nom_client', 'point_vente', 'nombre_personnes',
        'date_entree', 'table', 'statut',
    ]
    list_filter = ['statut', 'point_vente', 'date_entree']
    search_fields = [
        'nom_client', 'telephone', 'point_vente__nom',
        'table__numero', 'table__salle__nom',
    ]
    autocomplete_fields = ['point_vente', 'table']


@admin.register(SalleModel)
class SalleAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'point_vente', 'ordre', 'actif']
    list_filter = ['actif', 'point_vente']
    search_fields = ['code', 'nom', 'point_vente__nom']
    autocomplete_fields = ['point_vente']


@admin.register(TableModel)
class TableAdmin(ModelAdmin):
    list_display = ['numero', 'salle', 'capacite', 'statut', 'serveur_actuel', 'nombre_couverts', 'actif']
    list_filter = ['statut', 'salle', 'actif']
    search_fields = ['numero', 'salle__nom']
    autocomplete_fields = ['salle', 'serveur_actuel']


@admin.register(RecetteModel)
class RecetteAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_recette', 'prix_vente', 'temps_preparation_minutes', 'visible_dans_pos', 'actif']
    list_filter = ['type_recette', 'visible_dans_pos', 'actif']
    search_fields = ['code', 'nom']
    inlines = [IngredientInline, EtapeInline]


@admin.register(IngredientModel)
class IngredientAdmin(ModelAdmin):
    list_display = ['recette', 'produit', 'type_ingredient', 'quantite', 'unite', 'cout_unitaire']
    list_filter = ['type_ingredient']
    autocomplete_fields = ['recette', 'produit']


@admin.register(EtapePreparationModel)
class EtapePreparationAdmin(ModelAdmin):
    list_display = ['recette', 'ordre', 'instruction', 'duree_minutes']
    autocomplete_fields = ['recette']


@admin.register(MenuModel)
class MenuAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_menu', 'prix_vente', 'visible_dans_pos', 'actif']
    list_filter = ['type_menu', 'visible_dans_pos', 'actif']
    search_fields = ['code', 'nom']
    inlines = [LigneMenuInline]


@admin.register(LigneMenuModel)
class LigneMenuAdmin(ModelAdmin):
    list_display = ['menu', 'recette', 'groupe', 'type_ligne', 'quantite', 'prix_supplement']
    list_filter = ['groupe', 'type_ligne']
    autocomplete_fields = ['menu', 'recette']


@admin.register(Production)
class ProductionAdmin(ModelAdmin):
    list_display = ['numero', 'date_production', 'statut', 'entrepot_source', 'entrepot_dest']
    list_filter = ['statut', 'date_production']
    search_fields = ['numero']
    autocomplete_fields = ['produit_par', 'valide_par', 'entrepot_source', 'entrepot_dest']
    inlines = [ProductionLigneInline, ProductionIngredientInline]
    readonly_fields = ['date', 'created_at', 'updated_at']


@admin.register(ProductionLigne)
class ProductionLigneAdmin(ModelAdmin):
    list_display = ['production', 'recette', 'quantite']
    autocomplete_fields = ['production', 'recette']


@admin.register(ProductionIngredient)
class ProductionIngredientAdmin(ModelAdmin):
    list_display = ['production', 'produit', 'quantite', 'unite']
    autocomplete_fields = ['production', 'produit']


from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline, StackedInline

from .models import FileAttenteModel, TableModel, RecetteModel, IngredientModel, EtapePreparationModel, MenuModel, LigneMenuModel, Production, ProductionLigne, ProductionIngredient


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
    list_display = ['nom_client', 'telephone', 'nombre_personnes', 'date_entree', 'statut']
    list_filter = ['statut']


@admin.register(TableModel)
class TableAdmin(ModelAdmin):
    list_display = ['numero', 'capacite', 'statut', 'zone', 'nombre_couverts']
    list_filter = ['statut', 'zone']
    search_fields = ['numero']


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
    list_display = ['production', 'menu', 'quantite']
    autocomplete_fields = ['production', 'menu']


@admin.register(ProductionIngredient)
class ProductionIngredientAdmin(ModelAdmin):
    list_display = ['production', 'produit', 'quantite', 'unite']
    autocomplete_fields = ['production', 'produit']


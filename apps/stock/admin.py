from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import CategorieProduit, Produit, Entrepot, StockEntrepot, MouvementStock, Lot, SousUnite, Inventaire, LigneInventaire, BonEntree, LigneBonEntree, Domaine


class SousUniteInline(TabularInline):
    model = SousUnite
    extra = 1
    fields = ['nom', 'facteur', 'prix', 'actif']


class LotInline(TabularInline):
    model = Lot
    extra = 0
    fields = ['numero', 'quantite', 'quantite_restante', 'date_peremption', 'prix_achat', 'actif']


class StockEntrepotInline(TabularInline):
    model = StockEntrepot
    extra = 0
    fields = ['entrepot', 'quantite']
    readonly_fields = ['entrepot', 'quantite']


class LigneInventaireInline(TabularInline):
    model = LigneInventaire
    extra = 1
    fields = ['produit', 'quantite_theorique', 'quantite_reelle', 'ecart', 'notes']


class LigneBonEntreeInline(TabularInline):
    model = LigneBonEntree
    extra = 1
    fields = ['produit', 'quantite_commandee', 'quantite_recue', 'prix_achat']


@admin.register(CategorieProduit)
class CategorieProduitAdmin(ModelAdmin):
    list_display = ['nom', 'parent', 'actif']
    list_filter = ['actif']
    search_fields = ['nom']
    autocomplete_fields = ['parent']


@admin.register(Produit)
class ProduitAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'categorie', 'type_article', 'prix_achat', 'prix_vente', 'unite_base', 'actif']
    list_filter = ['type_article', 'actif', 'categorie', 'est_vendable']
    search_fields = ['code', 'nom', 'code_barre']
    autocomplete_fields = ['categorie']
    inlines = [SousUniteInline, LotInline]


@admin.register(Entrepot)
class EntrepotAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_entrepot', 'actif', 'responsable']
    list_filter = ['type_entrepot', 'actif']
    search_fields = ['code', 'nom']


@admin.register(StockEntrepot)
class StockEntrepotAdmin(ModelAdmin):
    list_display = ['entrepot', 'produit', 'quantite', 'updated_at']
    list_filter = ['entrepot']
    search_fields = ['produit__nom', 'produit__code']
    autocomplete_fields = ['entrepot', 'produit']


@admin.register(MouvementStock)
class MouvementStockAdmin(ModelAdmin):
    list_display = ['produit', 'type_mouvement', 'motif', 'quantite', 'entrepot_source', 'entrepot_dest', 'date_mouvement', 'utilisateur']
    list_filter = ['type_mouvement', 'motif', 'date_mouvement']
    search_fields = ['produit__nom', 'reference', 'raison']
    autocomplete_fields = ['produit', 'entrepot_source', 'entrepot_dest']


@admin.register(Lot)
class LotAdmin(ModelAdmin):
    list_display = ['numero', 'produit', 'quantite', 'quantite_restante', 'date_peremption', 'fournisseur', 'actif']
    list_filter = ['actif', 'date_peremption']
    search_fields = ['numero', 'produit__nom', 'fournisseur__nom']
    autocomplete_fields = ['produit', 'fournisseur']


@admin.register(SousUnite)
class SousUniteAdmin(ModelAdmin):
    list_display = ['produit', 'nom', 'facteur', 'prix', 'actif']
    list_filter = ['actif']
    autocomplete_fields = ['produit']


@admin.register(Inventaire)
class InventaireAdmin(ModelAdmin):
    list_display = ['code', 'entrepot', 'date_debut', 'date_fin', 'statut']
    list_filter = ['statut']
    search_fields = ['code']
    autocomplete_fields = ['entrepot']
    inlines = [LigneInventaireInline]
    readonly_fields = ['date_debut', 'created_at', 'updated_at']


@admin.register(LigneInventaire)
class LigneInventaireAdmin(ModelAdmin):
    list_display = ['inventaire', 'produit', 'quantite_theorique', 'quantite_reelle', 'ecart']
    autocomplete_fields = ['inventaire', 'produit']


@admin.register(BonEntree)
class BonEntreeAdmin(ModelAdmin):
    list_display = ['numero', 'fournisseur', 'entrepot', 'date_commande', 'date_reception', 'total', 'statut']
    list_filter = ['statut', 'date_commande', 'date_reception']
    search_fields = ['numero', 'reference_fournisseur', 'fournisseur__nom']
    autocomplete_fields = ['fournisseur', 'entrepot', 'created_by', 'valide_by']
    inlines = [LigneBonEntreeInline]
    readonly_fields = ['date_reception', 'created_at', 'total']


@admin.register(LigneBonEntree)
class LigneBonEntreeAdmin(ModelAdmin):
    list_display = ['bon_entree', 'produit', 'quantite_commandee', 'quantite_recue', 'prix_achat', 'montant']
    autocomplete_fields = ['bon_entree', 'produit', 'lot']


@admin.register(Domaine)
class DomaineAdmin(ModelAdmin):
    list_display = ['nom', 'icone', 'actif', 'ordre']
    list_editable = ['actif', 'ordre']



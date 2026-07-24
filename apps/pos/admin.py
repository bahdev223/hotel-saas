from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import (
    PointVente, Vente, LigneVente, SessionCaisse,
    Commande, LigneCommande, CaissePointVente, ShiftEmploye,
    AffectationPointVente, ComptageSession,
)


class LigneVenteInline(TabularInline):
    model = LigneVente
    extra = 1
    fields = ['produit', 'menu', 'quantite', 'prix_unitaire']


class LigneCommandeInline(TabularInline):
    model = LigneCommande
    extra = 1
    fields = ['produit', 'menu', 'quantite', 'prix_unitaire']


class AffectationInline(TabularInline):
    model = AffectationPointVente
    extra = 1


class CaissePointVenteInline(TabularInline):
    model = CaissePointVente
    extra = 1


@admin.register(PointVente)
class PointVenteAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type', 'actif']
    list_filter = ['type', 'actif']
    search_fields = ['code', 'nom']
    autocomplete_fields = []
    inlines = [CaissePointVenteInline, AffectationInline]


@admin.register(Vente)
class VenteAdmin(ModelAdmin):
    list_display = ['id', 'numero', 'point_vente', 'montant_total', 'mode_paiement', 'statut', 'caissier', 'created_at']
    list_filter = ['statut', 'mode_paiement', 'created_at']
    search_fields = ['numero', 'client_nom', 'id']
    autocomplete_fields = ['point_vente', 'caisse', 'session_caisse', 'caissier', 'client', 'table']
    inlines = [LigneVenteInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LigneVente)
class LigneVenteAdmin(ModelAdmin):
    list_display = ['vente', 'produit', 'menu', 'quantite', 'prix_unitaire', 'total_ligne']
    search_fields = ['vente__numero']
    autocomplete_fields = ['vente', 'produit', 'menu', 'recette']


@admin.register(SessionCaisse)
class SessionCaisseAdmin(ModelAdmin):
    list_display = ['caisse', 'point_vente', 'date_ouverture', 'date_fermeture',
                    'solde_initial', 'statut']
    list_filter = ['statut', 'date_ouverture']
    search_fields = ['caisse__nom', 'point_vente__nom']
    autocomplete_fields = ['caisse', 'point_vente', 'ouverte_par', 'fermee_par', 'validee_par', 'shift']
    readonly_fields = ['date_ouverture', 'created_at', 'updated_at']


@admin.register(ShiftEmploye)
class ShiftEmployeAdmin(ModelAdmin):
    list_display = ['affectation', 'debut_prevu', 'fin_prevue', 'statut']
    list_filter = ['statut']
    search_fields = ['affectation__employe__nom', 'affectation__employe__prenom']
    autocomplete_fields = ['affectation']


@admin.register(AffectationPointVente)
class AffectationPointVenteAdmin(ModelAdmin):
    list_display = ['employe', 'point_vente', 'role', 'peut_vendre', 'peut_encaisser', 'actif']
    list_filter = ['role', 'actif']
    search_fields = ['employe__nom', 'employe__prenom', 'point_vente__nom', 'point_vente__code']
    autocomplete_fields = ['employe', 'point_vente']


@admin.register(CaissePointVente)
class CaissePointVenteAdmin(ModelAdmin):
    list_display = ['point_vente', 'caisse', 'principale', 'actif']
    list_filter = ['principale', 'actif']
    autocomplete_fields = ['point_vente', 'caisse']


@admin.register(ComptageSession)
class ComptageSessionAdmin(ModelAdmin):
    list_display = ['session', 'especes_attendues', 'especes_comptees', 'ecart_especes', 'compte_par']
    autocomplete_fields = ['session', 'compte_par']


@admin.register(Commande)
class CommandeAdmin(ModelAdmin):
    list_display = ['numero', 'point_vente', 'type_commande', 'statut', 'montant_total', 'date_commande']
    list_filter = ['statut', 'type_commande', 'date_commande']
    search_fields = ['numero', 'client_nom', 'client_telephone']
    autocomplete_fields = ['point_vente', 'table', 'vente', 'created_by']
    inlines = [LigneCommandeInline]
    readonly_fields = ['date_commande', 'created_at', 'updated_at']


@admin.register(LigneCommande)
class LigneCommandeAdmin(ModelAdmin):
    list_display = ['commande', 'produit', 'menu', 'quantite', 'prix_unitaire']
    autocomplete_fields = ['commande', 'produit', 'menu', 'recette']

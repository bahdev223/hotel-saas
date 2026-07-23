from django.contrib import admin
from unfold.admin import ModelAdmin, TabularInline

from .models import PointVente, Vente, LigneVente, SessionCaisse, ChangementCaissier, Commande, LigneCommande


class LigneVenteInline(TabularInline):
    model = LigneVente
    extra = 1
    fields = ['produit', 'menu', 'quantite', 'prix_unitaire']


class LigneCommandeInline(TabularInline):
    model = LigneCommande
    extra = 1
    fields = ['produit', 'menu', 'quantite', 'prix_unitaire']


class ChangementCaissierInline(TabularInline):
    model = ChangementCaissier
    extra = 0
    fields = ['ancien_caissier', 'nouveau_caissier', 'date_changement', 'raison']
    readonly_fields = ['date_changement']


@admin.register(PointVente)
class PointVenteAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'emplacement', 'actif', 'utilisateur', 'responsable', 'caisse', 'entrepot']
    list_filter = ['emplacement', 'actif']
    search_fields = ['code', 'nom']
    autocomplete_fields = ['utilisateur', 'responsable', 'caisse', 'entrepot']


@admin.register(Vente)
class VenteAdmin(ModelAdmin):
    list_display = ['id', 'numero', 'point_vente', 'montant_total', 'mode_paiement', 'statut', 'caissier', 'created_at']
    list_filter = ['statut', 'mode_paiement', 'created_at']
    search_fields = ['numero', 'client_nom', 'id']
    autocomplete_fields = ['point_vente', 'caisse', 'session_caisse', 'caissier', 'table']
    inlines = [LigneVenteInline]
    readonly_fields = ['created_at', 'updated_at']


@admin.register(LigneVente)
class LigneVenteAdmin(ModelAdmin):
    list_display = ['vente', 'produit', 'menu', 'quantite', 'prix_unitaire', 'total_ligne']
    search_fields = ['vente__numero']
    autocomplete_fields = ['vente', 'produit', 'menu', 'recette']


@admin.register(SessionCaisse)
class SessionCaisseAdmin(ModelAdmin):
    list_display = ['caisse', 'point_vente', 'date_ouverture', 'date_fermeture', 'solde_initial', 'solde_attendu', 'solde_reel', 'difference', 'statut']
    list_filter = ['statut', 'date_ouverture']
    search_fields = ['caisse__nom', 'point_vente__nom']
    autocomplete_fields = ['caisse', 'point_vente', 'caissier_ouverture', 'caissier_fermeture']
    inlines = [ChangementCaissierInline]
    readonly_fields = ['date_ouverture', 'created_at', 'updated_at']


@admin.register(ChangementCaissier)
class ChangementCaissierAdmin(ModelAdmin):
    list_display = ['session', 'ancien_caissier', 'nouveau_caissier', 'date_changement', 'raison']
    list_filter = ['date_changement']
    autocomplete_fields = ['session', 'ancien_caissier', 'nouveau_caissier']


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


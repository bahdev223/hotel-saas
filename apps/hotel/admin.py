from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import (
    UniteModel, LocationModel,
    TypeChambre,
    TypeTarif, PlanTarifaire, TarifChambre, CreneauTarifaire,
    Reservation, ReservationChambre,
    Sejour,
    Occupant,
    ServiceSejour,
    HistoriqueStatutChambre,
)


@admin.register(UniteModel)
class UniteModelAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_unite', 'type_chambre', 'capacite', 'prix', 'statut', 'actif']
    list_filter = ['type_unite', 'statut', 'actif']
    search_fields = ['code', 'nom']
    list_editable = ['statut', 'actif']
    autocomplete_fields = ['type_chambre']


@admin.register(LocationModel)
class LocationModelAdmin(ModelAdmin):
    list_display = ['id', 'client', 'unite', 'type_location', 'date_debut', 'date_fin', 'montant_total', 'statut']
    list_filter = ['type_location', 'statut', 'date_debut']
    search_fields = ['id', 'client__nom', 'client__prenom', 'unite__code']
    autocomplete_fields = ['client', 'unite']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(TypeChambre)
class TypeChambreAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'categorie', 'capacite_par_defaut', 'actif', 'ordre']
    list_filter = ['categorie', 'actif']
    search_fields = ['code', 'nom']
    list_editable = ['actif', 'ordre']


@admin.register(TypeTarif)
class TypeTarifAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'unite_facturation', 'duree_minutes', 'actif', 'ordre']
    list_filter = ['unite_facturation', 'actif']
    search_fields = ['code', 'nom']
    list_editable = ['actif', 'ordre']


@admin.register(PlanTarifaire)
class PlanTarifaireAdmin(ModelAdmin):
    list_display = ['code', 'nom', 'type_client', 'priorite', 'actif']
    list_filter = ['type_client', 'actif']
    search_fields = ['code', 'nom']
    autocomplete_fields = ['etablissement']
    list_editable = ['priorite', 'actif']


@admin.register(TarifChambre)
class TarifChambreAdmin(ModelAdmin):
    list_display = ['type_chambre', 'plan_tarifaire', 'type_tarif', 'montant', 'actif']
    list_filter = ['actif', 'type_chambre', 'plan_tarifaire', 'type_tarif']
    search_fields = ['type_chambre__nom', 'plan_tarifaire__nom', 'type_tarif__nom']
    autocomplete_fields = ['etablissement', 'type_chambre', 'plan_tarifaire', 'type_tarif']
    list_editable = ['montant', 'actif']


@admin.register(CreneauTarifaire)
class CreneauTarifaireAdmin(ModelAdmin):
    list_display = ['nom', 'type_tarif', 'heure_debut', 'heure_fin', 'actif']
    list_filter = ['actif']
    search_fields = ['nom']
    autocomplete_fields = ['type_tarif']


@admin.register(Reservation)
class ReservationAdmin(ModelAdmin):
    list_display = ['code', 'client', 'date_arrivee_prevue', 'date_depart_prevue', 'statut', 'montant_total_estime']
    list_filter = ['statut', 'date_arrivee_prevue']
    search_fields = ['code', 'client__nom', 'client__prenom']
    autocomplete_fields = ['client', 'etablissement', 'cree_par', 'annule_par']
    readonly_fields = ['code', 'cree_le', 'modifie_le']


@admin.register(ReservationChambre)
class ReservationChambreAdmin(ModelAdmin):
    list_display = ['reservation', 'chambre', 'plan_tarifaire_nom', 'montant_unitaire', 'montant_total']
    autocomplete_fields = ['reservation', 'chambre', 'tarif_source']


@admin.register(Sejour)
class SejourAdmin(ModelAdmin):
    list_display = ['code', 'client', 'chambre', 'date_arrivee', 'statut', 'montant_total', 'cree_par']
    list_filter = ['statut']
    search_fields = ['code', 'client__nom', 'client__prenom', 'chambre__code']
    autocomplete_fields = ['client', 'chambre', 'reservation', 'etablissement', 'cree_par', 'ferme_par']
    readonly_fields = ['code', 'cree_le', 'modifie_le']


@admin.register(Occupant)
class OccupantAdmin(ModelAdmin):
    list_display = ['nom_complet', 'sejour', 'type_piece', 'numero_piece', 'est_principal']
    search_fields = ['nom_complet', 'numero_piece']
    autocomplete_fields = ['sejour']


@admin.register(ServiceSejour)
class ServiceSejourAdmin(ModelAdmin):
    list_display = ['nom', 'sejour', 'montant_total', 'quantite', 'cree_le']
    list_filter = ['cree_le']
    autocomplete_fields = ['sejour', 'facture']


@admin.register(HistoriqueStatutChambre)
class HistoriqueStatutChambreAdmin(ModelAdmin):
    list_display = ['chambre', 'ancien_statut', 'nouveau_statut', 'modifie_par', 'cree_le']
    list_filter = ['cree_le']
    search_fields = ['chambre__code']
    autocomplete_fields = ['chambre', 'modifie_par']
    readonly_fields = ['cree_le']

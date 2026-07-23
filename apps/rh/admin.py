# apps/rh/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from django import forms
from django.shortcuts import redirect
from django.urls import path
from django.utils.html import format_html
from django.contrib import messages

# Unfold imports
from unfold.admin import ModelAdmin, StackedInline, TabularInline
from unfold.contrib.forms.widgets import ArrayWidget

from .models import Employe, Contrat, Conge, Absence, Pointage, Departement, Poste
from .repositories import RhRepository


# ========== FORMULAIRES AVEC UNFOLD ==========

class EmployeAdminForm(forms.ModelForm):
    """Formulaire avec option de créer un compte User"""
    
    create_user = forms.BooleanField(
        required=False,
        label="Créer un compte utilisateur",
        help_text="Cochez pour créer un compte de connexion pour cet employé"
    )
    username = forms.CharField(
        required=False,
        label="Nom d'utilisateur",
        help_text="Laisser vide pour utiliser le matricule"
    )
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput,
        label="Mot de passe",
        help_text="Laisser vide pour utiliser le matricule par défaut"
    )
    
    class Meta:
        model = Employe
        fields = '__all__'
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 3}),
            'date_naissance': forms.DateInput(attrs={'type': 'date'}),
            'date_embauche': forms.DateInput(attrs={'type': 'date'}),
            'date_sortie': forms.DateInput(attrs={'type': 'date'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        create_user = cleaned_data.get('create_user')
        username = cleaned_data.get('username')
        
        if create_user:
            if not username:
                cleaned_data['username'] = cleaned_data.get('matricule')
        
        return cleaned_data


class ContratInline(TabularInline):
    model = Contrat
    extra = 1
    fields = ['type_contrat', 'date_debut', 'date_fin', 'salaire_brut_mensuel', 'actif']
    classes = ['collapse']


class CongeInline(TabularInline):
    model = Conge
    extra = 0
    fields = ['date_debut', 'date_fin', 'nb_jours_ouvrables', 'statut']
    readonly_fields = ['statut']
    classes = ['collapse']


# ========== ADMIN EMPLOYE AVEC UNFOLD ==========

@admin.register(Employe)
class EmployeAdmin(ModelAdmin):
    form = EmployeAdminForm
    inlines = [ContratInline, CongeInline]
    
    list_display = [
        'matricule', 'nom', 'prenom', 'poste', 'departement',
        'display_point_vente', 'display_compte_status', 'display_user_link', 'actif'
    ]
    list_filter = ['actif', 'departement', 'poste', 'situation_familiale']
    search_fields = ['matricule', 'nom', 'prenom', 'email', 'telephone']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Identité', {
            'fields': ('matricule', 'nom', 'prenom', 'date_naissance', 'photo'),
            'classes': ['tab']
        }),
        ('Contact', {
            'fields': ('email', 'telephone', 'adresse'),
            'classes': ['tab']
        }),
        ('Professionnel', {
            'fields': ('date_embauche', 'departement', 'poste', 'point_vente'),
            'classes': ['tab']
        }),
        ('Situation familiale', {
            'fields': ('situation_familiale', 'nombre_enfants'),
            'classes': ['tab']
        }),
        ('Conjoint(e)', {
            'fields': ('conjoint_civilite', 'conjoint_nom', 'conjoint_prenom', 'conjoint_contact'),
            'classes': ['collapse', 'tab']
        }),
        ('Personne de référence', {
            'fields': ('personne_reference_nom', 'personne_reference_prenom', 'personne_reference_contact'),
            'classes': ['collapse', 'tab']
        }),
        ('Diplôme et description', {
            'fields': ('diplome', 'description'),
            'classes': ['collapse', 'tab']
        }),
        ('Statut', {
            'fields': ('actif', 'date_sortie'),
            'classes': ['tab']
        }),
        ('Compte utilisateur', {
            'fields': ('user',),
            'classes': ['collapse', 'tab']
        }),
        ('Création compte', {
            'fields': ('create_user', 'username', 'password'),
            'classes': ['collapse', 'tab']
        }),
    )
    
    def display_user_link(self, obj):
        if obj.user:
            return format_html(f'<a href="/admin/authentication/user/{obj.user.id}/change/" class="text-primary hover:underline">{obj.user.username}</a>')
        return '-'
    display_user_link.short_description = 'Utilisateur'

    def display_point_vente(self, obj):
        if obj.point_vente:
            return format_html(f'<a href="/admin/pos/pointvente/{obj.point_vente.id}/change/" class="text-primary hover:underline">{obj.point_vente.nom}</a>')
        return '-'
    display_point_vente.short_description = 'Point de vente'

    def display_compte_status(self, obj):
        if obj.user:
            if obj.user.is_active:
                return format_html('<span class="bg-green-100 text-green-800 px-2 py-1 rounded">✓ Actif</span>')
            else:
                return format_html('<span class="bg-orange-100 text-orange-800 px-2 py-1 rounded">⚠ Désactivé</span>')
        return format_html('<span class="bg-red-100 text-red-800 px-2 py-1 rounded">✗ Pas de compte</span>')
    display_compte_status.short_description = 'Compte'
    
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        
        create_user = form.cleaned_data.get('create_user')
        if create_user:
            username = form.cleaned_data.get('username') or obj.matricule
            password = form.cleaned_data.get('password') or obj.matricule
            
            if username:
                user = RhRepository.creer_compte_utilisateur(
                    username=username,
                    password=password,
                    email=obj.email
                )
                RhRepository.lier_employe_a_user(obj.matricule, user)
                messages.success(request, f'Compte utilisateur créé pour {obj.nom} {obj.prenom}')


# ========== AUTRES ADMINS ==========

@admin.register(Contrat)
class ContratAdmin(ModelAdmin):
    list_display = ['id_contrat', 'employe', 'type_contrat', 'date_debut', 'date_fin', 'actif']
    list_filter = ['type_contrat', 'actif', 'statut_cadre']
    search_fields = ['id_contrat', 'employe__matricule', 'employe__nom']
    autocomplete_fields = ['employe']


@admin.register(Conge)
class CongeAdmin(ModelAdmin):
    list_display = ['id_conge', 'employe', 'date_debut', 'date_fin', 'nb_jours_ouvrables', 'statut']
    list_filter = ['statut']
    search_fields = ['id_conge', 'employe__matricule', 'employe__nom']
    autocomplete_fields = ['employe']
    
    actions = ['valider_conges', 'refuser_conges']
    
    def valider_conges(self, request, queryset):
        queryset.update(statut='Validé')
        self.message_user(request, f'{queryset.count()} congé(s) validé(s)')
    valider_conges.short_description = 'Valider les congés sélectionnés'
    
    def refuser_conges(self, request, queryset):
        queryset.update(statut='Refusé')
        self.message_user(request, f'{queryset.count()} congé(s) refusé(s)')
    refuser_conges.short_description = 'Refuser les congés sélectionnés'


@admin.register(Absence)
class AbsenceAdmin(ModelAdmin):
    list_display = ['id_absence', 'employe', 'date_debut', 'date_fin', 'type_absence', 'nb_jours', 'validee']
    list_filter = ['type_absence', 'validee']
    search_fields = ['id_absence', 'employe__matricule', 'employe__nom']
    autocomplete_fields = ['employe']


@admin.register(Pointage)
class PointageAdmin(ModelAdmin):
    list_display = ['id_pointage', 'employe', 'date_pointage', 'heure_entree', 'heure_sortie', 'heures_travaillees']
    list_filter = ['date_pointage', 'est_justifie']
    search_fields = ['id_pointage', 'employe__matricule', 'employe__nom']
    autocomplete_fields = ['employe']


@admin.register(Departement)
class DepartementAdmin(ModelAdmin):
    list_display = ['code', 'libelle', 'responsable', 'actif']
    search_fields = ['code', 'libelle']
    autocomplete_fields = ['responsable']


@admin.register(Poste)
class PosteAdmin(ModelAdmin):
    list_display = ['code', 'intitule', 'classification', 'coefficient']
    list_filter = ['classification']
    search_fields = ['code', 'intitule']


# ========== L'AUTHENTIFICATION EST GÉRÉE PAR apps.authentication.admin ==========


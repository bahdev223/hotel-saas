# apps/authentication/admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin, GroupAdmin
from django.contrib.auth.models import User, Group
from django import forms
from django.utils.html import format_html
from unfold.admin import ModelAdmin, StackedInline
from django.urls import path
from django.shortcuts import redirect
from django.contrib import messages

from .models import Profile, PasswordResetToken


class ProfileInline(StackedInline):
    """Profil utilisateur dans l'admin User"""
    model = Profile
    can_delete = False
    fields = ['telephone', 'matricule_employe', 'theme', 'notifications_email', 'derniere_connexion_ip']
    readonly_fields = ['derniere_connexion_ip']


# 🔥 FORMULAIRE PERSONNALISÉ AVEC LISTE DÉROULANTE
class UserCreationForm(forms.ModelForm):
    """Formulaire de création d'utilisateur avec sélection d'employé"""
    
    from apps.rh.models import Employe
    
    # Liste déroulante des employés sans compte utilisateur
    employe = forms.ModelChoiceField(
        queryset=Employe.objects.filter(user__isnull=True, actif=True),
        required=False,
        label="👤 Employé à associer",
        help_text="Sélectionnez un employé existant (sans compte utilisateur)"
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ajouter des classes CSS pour Unfold
        self.fields['employe'].widget.attrs.update({'class': 'select2'})
    
    def save(self, commit=True):
        user = super().save(commit=False)
        
        if commit:
            user.save()
            # Associer l'employé si sélectionné
            employe = self.cleaned_data.get('employe')
            if employe:
                employe.user = user
                employe.save()
                # Mettre à jour le profil avec le matricule
                if hasattr(user, 'profile'):
                    user.profile.matricule_employe = employe.matricule
                    user.profile.save()
        
        return user


class UserChangeForm(forms.ModelForm):
    """Formulaire de modification d'utilisateur avec sélection d'employé"""
    
    from apps.rh.models import Employe
    
    # Liste déroulante de TOUS les employés (liés ou non)
    employe = forms.ModelChoiceField(
        queryset=Employe.objects.all(),
        required=False,
        label="👤 Employé associé",
        help_text="Sélectionnez l'employé lié à ce compte"
    )
    
    class Meta:
        model = User
        fields = ('username', 'email', 'first_name', 'last_name', 'is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['employe'].widget.attrs.update({'class': 'select2'})
        # Pré-sélectionner l'employé lié
        if self.instance and hasattr(self.instance, 'employe'):
            self.fields['employe'].initial = self.instance.employe
    
    def save(self, commit=True):
        user = super().save(commit=commit)
        employe = self.cleaned_data.get('employe')
        
        # Retirer l'ancienne association si changée
        if hasattr(user, 'employe') and user.employe != employe:
            old_employe = user.employe
            old_employe.user = None
            old_employe.save()
        
        # Nouvelle association
        if employe:
            employe.user = user
            employe.save()
            if hasattr(user, 'profile'):
                user.profile.matricule_employe = employe.matricule
                user.profile.save()
        elif hasattr(user, 'profile'):
            user.profile.matricule_employe = ''
            user.profile.save()
        
        return user


class CustomUserAdmin(UserAdmin, ModelAdmin):
    """Administration personnalisée des utilisateurs avec Unfold"""
    
    # 🔥 UTILISATION DES FORMULAIRES PERSONNALISÉS
    form = UserChangeForm
    add_form = UserCreationForm
    
    inlines = [ProfileInline]
    
    list_display = [
        'username', 
        'email', 
        'first_name', 
        'last_name', 
        'display_employe',  # 🔥 MODIFIÉ
        'display_groups', 
        'display_role',
        'is_active',
        'display_last_login'
    ]
    
    list_filter = [
        'is_staff', 
        'is_active', 
        'is_superuser',
        'groups',
        'date_joined'
    ]
    
    search_fields = ['username', 'email', 'first_name', 'last_name', 'profile__telephone', 'employe__matricule', 'employe__nom']
    
    list_per_page = 20
    
    # 🔥 FIELDSETS AVEC LE CHAMP EMPLOYE
    fieldsets = (
        ('Informations personnelles', {
            'fields': ('username', 'password', 'first_name', 'last_name', 'email', 'employe'),
            'classes': ['tab']
        }),
        ('Permissions', {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
            'classes': ['tab']
        }),
        ('Dates importantes', {
            'fields': ('last_login', 'date_joined'),
            'classes': ['tab', 'collapse']
        }),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'password1', 'password2', 'email', 'first_name', 'last_name', 'employe'),
        }),
    )
    
    filter_horizontal = ['groups', 'user_permissions']
    
    def display_employe(self, obj):
        """🔥 Affiche l'employé associé"""
        if hasattr(obj, 'employe') and obj.employe:
            employe = obj.employe
            return format_html(
                f'<a href="/admin/rh/employe/{employe.id}/change/" class="text-primary hover:underline">{employe.matricule} - {employe.nom} {employe.prenom}</a>'
            )
        return format_html('<span class="text-gray-400">Aucun employé</span>')
    display_employe.short_description = 'Employé'
    
    def display_groups(self, obj):
        """Affiche les groupes de l'utilisateur"""
        groups = obj.groups.all()
        if groups:
            badges = []
            for group in groups:
                badges.append(f'<span class="px-2 py-1 text-xs rounded bg-primary-100 text-primary-800">{group.name}</span>')
            return format_html(' '.join(badges))
        return format_html('<span class="text-gray-400">Aucun groupe</span>')
    display_groups.short_description = 'Groupes'
    
    def display_role(self, obj):
        """Affiche le rôle principal (premier groupe)"""
        group = obj.groups.first()
        if group:
            colors = {
                'ADMINISTRATEUR': 'bg-red-100 text-red-800',
                'RECEPTION': 'bg-green-100 text-green-800',
                'COMPTABILITE': 'bg-blue-100 text-blue-800',
                'RESTAURANT': 'bg-orange-100 text-orange-800',
                'BAR': 'bg-purple-100 text-purple-800',
                'MAINTENANCE': 'bg-yellow-100 text-yellow-800',
                'DIRECTION': 'bg-indigo-100 text-indigo-800',
                'RH': 'bg-pink-100 text-pink-800',
            }
            color = colors.get(group.name, 'bg-gray-100 text-gray-800')
            return format_html(f'<span class="px-2 py-1 rounded text-xs {color}">{group.name}</span>')
        return format_html('<span class="text-gray-400">-</span>')
    
    display_role.short_description = 'Rôle'
    
    def display_last_login(self, obj):
        """Affiche la dernière connexion formatée"""
        if obj.last_login:
            return obj.last_login.strftime('%d/%m/%Y %H:%M')
        return '-'
    
    display_last_login.short_description = 'Dernière connexion'
    
    actions = ['activer_utilisateurs', 'desactiver_utilisateurs', 'reinitialiser_mdp_action', 'dissocier_employe']
    
    def activer_utilisateurs(self, request, queryset):
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} utilisateur(s) activé(s)', messages.SUCCESS)
    activer_utilisateurs.short_description = 'Activer les utilisateurs sélectionnés'
    
    def desactiver_utilisateurs(self, request, queryset):
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} utilisateur(s) désactivé(s)', messages.SUCCESS)
    desactiver_utilisateurs.short_description = 'Désactiver les utilisateurs sélectionnés'
    
    def reinitialiser_mdp_action(self, request, queryset):
        from django.utils.crypto import get_random_string
        for user in queryset:
            new_password = get_random_string(8)
            user.set_password(new_password)
            user.save()
            self.message_user(request, f'Mot de passe de {user.username} réinitialisé', messages.SUCCESS)
    reinitialiser_mdp_action.short_description = 'Réinitialiser le mot de passe des utilisateurs sélectionnés'
    
    def dissocier_employe(self, request, queryset):
        """Dissocie l'employé des utilisateurs sélectionnés"""
        from apps.rh.models import Employe
        count = 0
        for user in queryset:
            if hasattr(user, 'employe') and user.employe:
                employe = user.employe
                employe.user = None
                employe.save()
                count += 1
        self.message_user(request, f'{count} employé(s) dissocié(s)', messages.SUCCESS)
    dissocier_employe.short_description = 'Dissocier l\'employé'


@admin.register(Profile)
class ProfileAdmin(ModelAdmin):
    """Administration des profils"""
    list_display = ['user', 'telephone', 'matricule_employe', 'theme', 'created_at']
    list_filter = ['theme', 'notifications_email']
    search_fields = ['user__username', 'user__email', 'telephone', 'matricule_employe']
    readonly_fields = ['created_at', 'updated_at', 'derniere_connexion_ip']
    
    fieldsets = (
        ('Informations', {
            'fields': ('user', 'telephone', 'matricule_employe', 'avatar')
        }),
        ('Préférences', {
            'fields': ('theme', 'notifications_email')
        }),
        ('Audit', {
            'fields': ('derniere_connexion_ip', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(PasswordResetToken)
class PasswordResetTokenAdmin(ModelAdmin):
    """Administration des tokens de réinitialisation"""
    list_display = ['user', 'token_short', 'created_at', 'expires_at', 'is_valid_display', 'used']
    list_filter = ['used', 'created_at', 'expires_at']
    search_fields = ['user__username', 'user__email', 'token']
    readonly_fields = ['token', 'created_at', 'expires_at']
    
    def token_short(self, obj):
        return str(obj.token)[:8] + '...'
    token_short.short_description = 'Token'
    
    def is_valid_display(self, obj):
        if obj.is_valid():
            return format_html('<span class="px-2 py-1 text-green-800 bg-green-100 rounded">Valide</span>')
        return format_html('<span class="px-2 py-1 text-red-800 bg-red-100 rounded">Expiré</span>')
    is_valid_display.short_description = 'Statut'


# Réenregistrer User
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)


class CustomGroupAdmin(GroupAdmin, ModelAdmin):
    """Administration personnalisée des groupes"""
    list_display = ['name', 'display_permissions', 'user_count']
    search_fields = ['name']
    filter_horizontal = ['permissions']
    
    def display_permissions(self, obj):
        count = obj.permissions.count()
        return format_html(f'<span class="badge badge-info">{count} permissions</span>')
    display_permissions.short_description = 'Permissions'
    
    def user_count(self, obj):
        count = obj.user_set.count()
        return format_html(f'<span class="badge badge-primary">{count} utilisateur(s)</span>')
    user_count.short_description = 'Utilisateurs'


admin.site.unregister(Group)
admin.site.register(Group, CustomGroupAdmin)


# ========== ACTIONS RAPIDES DANS L'ADMIN ==========

def get_admin_urls():
    from django.urls import path
    from django.shortcuts import render
    from django.contrib.auth.decorators import login_required
    
    @login_required
    def admin_dashboard(request):
        from django.contrib.auth.models import User, Group
        from apps.rh.models import Departement, Poste, Employe
        
        stats = {
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_groups': Group.objects.count(),
            'total_departements': Departement.objects.count(),
            'total_postes': Poste.objects.count(),
            'total_employes': Employe.objects.count(),
        }
        
        context = {
            'stats': stats,
            'title': 'Administration - Dashboard'
        }
        return render(request, 'admin/dashboard.html', context)
    
    return [
        path('dashboard/', admin_dashboard, name='admin_dashboard'),
    ]


if hasattr(admin.site, 'get_urls'):
    original_get_urls = admin.site.get_urls
    
    def custom_get_urls():
        urls = original_get_urls()
        custom_urls = get_admin_urls()
        return custom_urls + urls
    
    admin.site.get_urls = custom_get_urls
    
    
    
from django.contrib import admin
from django import forms
from django.utils.html import format_html
from django.shortcuts import redirect
from django.urls import path
from django.contrib import messages

from unfold.admin import ModelAdmin

from .models import Client


class ClientAdminForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = '__all__'
        widgets = {
            'adresse': forms.Textarea(attrs={'rows': 3}),
        }


@admin.register(Client)
class ClientAdmin(ModelAdmin):
    form = ClientAdminForm

    list_display = [
        'id',
        'nom',
        'prenom',
        'telephone',
        'email',
        'display_type',
        'display_statut',
        'display_actions'
    ]
    list_filter = ['type_client', 'statut']
    search_fields = ['id', 'nom', 'prenom', 'telephone', 'email']

    fieldsets = (
        ('Identité', {
            'fields': ('id', 'nom', 'prenom', 'telephone', 'email', 'adresse', 'sexe', 'date_naissance'),
            'classes': ['tab']
        }),
        ('Catégorie', {
            'fields': ('type_client', 'statut'),
            'classes': ['tab']
        }),
        ('Documents', {
            'fields': ('piece_identite', 'numero_piece', 'identifiant_fiscal'),
            'classes': ['tab']
        }),
        ('Informations', {
            'fields': ('notes', 'date_inscription'),
            'classes': ['tab', 'collapse']
        }),
    )
    readonly_fields = ['date_inscription', 'created_at', 'updated_at']

    def display_type(self, obj):
        types = {
            'PARTICULIER': 'Particulier',
            'ENTREPRISE': 'Entreprise',
            'AGENCE': 'Agence',
        }
        return types.get(obj.type_client, obj.type_client)
    display_type.short_description = 'Type'

    def display_statut(self, obj):
        if obj.statut == 'ACTIF':
            return format_html('<span class="bg-green-100 text-green-800 px-2 py-1 rounded">Actif</span>')
        elif obj.statut == 'INACTIF':
            return format_html('<span class="bg-gray-100 text-gray-800 px-2 py-1 rounded">Inactif</span>')
        else:
            return format_html('<span class="bg-red-100 text-red-800 px-2 py-1 rounded">Blacklisté</span>')
    display_statut.short_description = 'Statut'

    def display_actions(self, obj):
        return format_html('''
            <div class="flex space-x-2">
                <a href="changer-statut/{}/actif/" class="bg-green-500 text-white px-2 py-1 rounded text-xs no-underline">Actif</a>
                <a href="changer-statut/{}/inactif/" class="bg-gray-500 text-white px-2 py-1 rounded text-xs no-underline">Inactif</a>
                <a href="changer-statut/{}/blacklist/" class="bg-red-500 text-white px-2 py-1 rounded text-xs no-underline">Blacklist</a>
            </div>
        ''', obj.id, obj.id, obj.id)
    display_actions.short_description = 'Actions rapides'

    def get_urls(self):
        urls = super().get_urls()
        custom_urls = [
            path('changer-statut/<str:client_id>/<str:statut>/',
                 self.admin_site.admin_view(self.changer_statut),
                 name='changer_statut_client'),
        ]
        return custom_urls + urls

    def changer_statut(self, request, client_id, statut):
        try:
            statut_map = {
                'actif': 'ACTIF',
                'inactif': 'INACTIF',
                'blacklist': 'BLACKLIST',
            }
            nouveau_statut = statut_map.get(statut, 'ACTIF')
            Client.objects.filter(id=client_id).update(statut=nouveau_statut)
            messages.success(request, f'Statut du client {client_id} changé avec succès')
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
        return redirect('admin:clients_client_changelist')

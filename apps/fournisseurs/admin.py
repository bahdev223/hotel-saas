from django.contrib import admin
from .models import Fournisseur


@admin.register(Fournisseur)
class FournisseurAdmin(admin.ModelAdmin):
    list_display = ['code', 'nom', 'telephone', 'email', 'contact', 'actif']
    list_filter = ['actif']
    search_fields = ['code', 'nom', 'telephone', 'email']

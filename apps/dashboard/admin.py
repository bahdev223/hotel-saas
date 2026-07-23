from django.contrib import admin
from unfold.admin import ModelAdmin

from .models import DashboardWidget, UserDashboardPreference


@admin.register(DashboardWidget)
class DashboardWidgetAdmin(ModelAdmin):
    list_display = ['code', 'titre', 'type_widget', 'ordre', 'taille', 'actif']
    list_filter = ['type_widget', 'actif', 'taille']
    search_fields = ['code', 'titre']
    list_editable = ['ordre', 'actif']


@admin.register(UserDashboardPreference)
class UserDashboardPreferenceAdmin(ModelAdmin):
    list_display = ['user', 'widgets_count', 'refresh_interval', 'updated_at']
    search_fields = ['user__username', 'user__email']
    filter_horizontal = ['widgets_actifs']
    autocomplete_fields = ['user']

    def widgets_count(self, obj):
        return obj.widgets_actifs.count()
    widgets_count.short_description = 'Widgets actifs'

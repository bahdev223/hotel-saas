# apps/dashboard/models.py
"""
Modèles pour le dashboard (widgets, préférences utilisateur)
"""

from django.db import models
from django.contrib.auth.models import User


class DashboardWidget(models.Model):
    """Widget personnalisable pour le dashboard"""
    
    WIDGET_TYPES = [
        ('OCCUPATION', 'Taux d\'occupation'),
        ('CA_JOUR', 'Chiffre d\'affaires du jour'),
        ('COMMANDES_EN_COURS', 'Commandes en cours'),
        ('STOCK_ALERTE', 'Alertes stock'),
        ('TOP_PLATS', 'Plats les plus commandés'),
        ('RESERVATIONS', 'Réservations à venir'),
        ('ACTIVITE_RECENTE', 'Activité récente'),
        ('CHAMBRES', 'État des chambres'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    titre = models.CharField(max_length=100)
    type_widget = models.CharField(max_length=30, choices=WIDGET_TYPES)
    ordre = models.IntegerField(default=0)
    actif = models.BooleanField(default=True)
    taille = models.CharField(max_length=10, default='md')  # sm, md, lg, xl
    
    class Meta:
        db_table = 'dashboard_widgets'
        verbose_name = 'Widget'
        verbose_name_plural = 'Widgets'
        ordering = ['ordre']
    
    def __str__(self):
        return self.titre


class UserDashboardPreference(models.Model):
    """Préférences de dashboard par utilisateur"""
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='dashboard_prefs')
    widgets_actifs = models.ManyToManyField(DashboardWidget, blank=True)
    refresh_interval = models.IntegerField(default=30, help_text="Secondes")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'dashboard_user_prefs'
        verbose_name = 'Préférence dashboard'
        verbose_name_plural = 'Préférences dashboards'
    
    def __str__(self):
        return f"Préférences de {self.user.username}"
    
    
    
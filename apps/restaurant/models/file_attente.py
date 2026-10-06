# apps/restaurant/models/file_attente.py
from django.db import models


class FileAttenteModel(models.Model):
    """File d'attente des clients"""
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('PLACE', 'Placé'),
        ('PARTI', 'Parti'),
    ]
    
    nombre_personnes = models.IntegerField()
    nom_client = models.CharField(max_length=100, blank=True, null=True)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    date_entree = models.DateTimeField(auto_now_add=True)
    point_vente = models.ForeignKey(
        'pos.PointVente',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='file_attente_restaurant',
    )
    table_assigned = models.CharField(max_length=10, blank=True, null=True)
    table = models.ForeignKey(
        'restaurant.TableModel',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='placements_file_attente',
    )
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    
    class Meta:
        db_table = 'restaurant_file_attente'
        verbose_name = 'File d\'attente'
        verbose_name_plural = 'Files d\'attente'
        ordering = ['date_entree']
    
    def __str__(self):
        return f"{self.nom_client or 'Client'} - {self.nombre_personnes} pers."
    
    
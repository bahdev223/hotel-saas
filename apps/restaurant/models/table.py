from django.db import models


class TableModel(models.Model):
    """Table du restaurant"""

    STATUT_CHOICES = [
        ('LIBRE', 'Libre'),
        ('OCCUPEE', 'Occupée'),
        ('RESERVEE', 'Réservée'),
        ('EN_ATTENTE', 'En attente'),
    ]

    numero = models.CharField(max_length=10, unique=True)
    capacite = models.IntegerField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='LIBRE')
    zone = models.CharField(max_length=50, blank=True, null=True)
    serveur_id = models.CharField(max_length=50, blank=True, null=True)
    commande_id = models.CharField(max_length=50, blank=True, null=True)
    heure_arrivee = models.DateTimeField(blank=True, null=True)
    nombre_couverts = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'restaurant_tables'
        verbose_name = 'Table'
        verbose_name_plural = 'Tables'
        ordering = ['numero']

    def __str__(self):
        return f"Table {self.numero} ({self.capacite} pers.)"

from django.db import models


class TableModel(models.Model):
    """Table opérationnelle rattachée à une salle Restaurant."""

    STATUT_CHOICES = [
        ('LIBRE', 'Libre'),
        ('OCCUPEE', 'Occupée'),
        ('COMMANDE_EN_COURS', 'Commande en cours'),
        ('A_ENCAISSER', 'À encaisser'),
        ('RESERVEE', 'Réservée'),
        ('EN_ATTENTE', 'En attente'),
        ('HORS_SERVICE', 'Hors service'),
    ]

    numero = models.CharField(max_length=10)
    salle = models.ForeignKey(
        'restaurant.SalleModel',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='tables',
    )
    capacite = models.PositiveSmallIntegerField()
    statut = models.CharField(max_length=30, choices=STATUT_CHOICES, default='LIBRE')
    actif = models.BooleanField(default=True)

    # Compatibilité historique. Les nouveaux flux utilisent salle + Commande.table.
    zone = models.CharField(max_length=50, blank=True, null=True)
    serveur_id = models.CharField(max_length=50, blank=True, null=True)
    commande_id = models.CharField(max_length=50, blank=True, null=True)

    serveur_actuel = models.ForeignKey(
        'rh.Employe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tables_restaurant_actuelles',
    )
    heure_arrivee = models.DateTimeField(blank=True, null=True)
    nombre_couverts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'restaurant_tables'
        verbose_name = 'Table'
        verbose_name_plural = 'Tables'
        ordering = ['numero']
        constraints = [
            models.UniqueConstraint(
                fields=['salle', 'numero'],
                name='unique_table_numero_par_salle',
            ),
        ]

    def __str__(self):
        salle = f" · {self.salle.nom}" if self.salle_id else ""
        return f"Table {self.numero}{salle} ({self.capacite} pers.)"

    @property
    def point_vente(self):
        return self.salle.point_vente if self.salle_id else None

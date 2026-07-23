from django.db import models


class Entrepot(models.Model):
    """Entrepôt  point de stock """

    TYPE_CHOICES = [
        ('CENTRAL', 'Magasin Central'),
        ('BAR', 'Bar'),
        ('BRASSERIE', 'Brasserie'),
        ('RESTAURANT', 'Restaurant'),
        ('HOTEL', 'Hôtel'),
        ('CUISINE', 'Cuisine'),
        ('SPA', 'Spa'),
        ('MINIBAR', 'Mini-bar'),
    ]

    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    type_entrepot = models.CharField(max_length=20, choices=TYPE_CHOICES)
    actif = models.BooleanField(default=True)
    responsable = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'stock_entrepots'
        verbose_name = 'Entrepôt'
        verbose_name_plural = 'Entrepôts'
        ordering = ['nom']

    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    
    

# apps/hotel/models/unite.py
from django.db import models
import uuid

def generate_unite_id():
    return f"U{uuid.uuid4().hex[:8].upper()}"

class UniteModel(models.Model):
    TYPE_CHOICES = [
        ('CHAMBRE', 'Chambre'),
        ('VIP', 'VIP'),
        ('SALLE', 'Salle'),
        ('ESPACE', 'Espace'),
        ('ESPACE_BAR', 'Espace + Bar'),
        ('BAR', 'Bar VIP'),
    ]
    
    STATUT_CHOICES = [
        ('DISPONIBLE', 'Disponible'),
        ('OCCUPEE', 'Occupée'),
        ('NETTOYAGE', 'Nettoyage'),
        ('HORS_SERVICE', 'Hors service'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, default=generate_unite_id, editable=False)
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    type_unite = models.CharField(max_length=20, choices=TYPE_CHOICES, default='CHAMBRE')
    capacite = models.IntegerField(default=1)
    surface_m2 = models.FloatField(null=True, blank=True)
    equipements = models.JSONField(default=list)
    prix = models.DecimalField(max_digits=10, decimal_places=2, help_text="Prix par heure")
    prix_jour = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Prix par jour")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='DISPONIBLE')
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='hotel/unites/', null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hotel_unites'
        verbose_name = 'Chambre'
        verbose_name_plural = 'Chambres'
        ordering = ['type_unite', 'code']

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def occuper(self):
        self.statut = 'OCCUPEE'
        self.save()

    def liberer(self):
        self.statut = 'DISPONIBLE'
        self.save()

    def reserver(self):
        self.statut = 'RESERVEE'
        self.save()
        
        
        
# apps/pos/models/point_vente.py
from django.db import models
from django.contrib.auth.models import User, Group
from apps.tresorerie.models import Caisse
from apps.rh.models import Employe
from apps.stock.models import Entrepot
from ..constants import POINT_VENTE_GROUP_MAPPING


class PointVenteEntrepot(models.Model):
    """Liaison many-to-many entre un point de vente et plusieurs entrepôts"""

    point_vente = models.ForeignKey(
        'PointVente', on_delete=models.CASCADE, related_name='entrepots_autorises'
    )
    entrepot = models.ForeignKey(
        Entrepot, on_delete=models.CASCADE, related_name='points_vente_autorises'
    )

    class Meta:
        db_table = 'pos_point_vente_entrepots'
        unique_together = ('point_vente', 'entrepot')
        verbose_name = "Liaison point de vente ↔ entrepôt"
        verbose_name_plural = "Liaisons points de vente ↔ entrepôts"

    def __str__(self):
        return f"{self.point_vente.nom} → {self.entrepot.nom}"

class PointVente(models.Model):
    """Point de vente physique (Restaurant, Bar, Réception, etc.)"""

    EMPLACEMENT_CHOICES = [
        ('RESTAURANT', 'Restaurant principal'),
        ('BAR', 'Bar piscine'),
        ('VIP', 'VIP Lounge'),
        ('TERRASSE', 'Terrasse'),
        ('RECEPTION', 'Réception hôtel'),
        ('ROOM_SERVICE', 'Room service'),
        ('GUICHET', 'Guichet unique'),
    ]

    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    emplacement = models.CharField(max_length=20, choices=EMPLACEMENT_CHOICES)
    actif = models.BooleanField(default=True)
    
    # L'utilisateur Django qui peut se connecter à ce POS
    utilisateur = models.OneToOneField(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='point_vente_associe'
    )
    
    # L'employé responsable de ce point de vente
    responsable = models.ForeignKey(
        Employe,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='points_vente'
    )
    
    caisse = models.OneToOneField(
        Caisse,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='point_vente_associe'
    )
    imprimante_nom = models.CharField(max_length=100, blank=True, null=True)
    impression_auto = models.BooleanField(default=True)
    
    entrepot = models.ForeignKey(
        Entrepot,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='points_vente'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pos_points_vente'
        verbose_name = 'Point de vente'
        verbose_name_plural = 'Points de vente'

    def __str__(self):
        return f"{self.nom} ({self.get_emplacement_display()})"
    
    def creer_utilisateur(self, password='pos123456'):
        """Crée automatiquement un utilisateur pour ce point de vente"""
        if self.utilisateur:
            return self.utilisateur
        
        username = f"pos_{self.code.lower()}"
        email = f"{self.code.lower()}@hotel.local"
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=self.nom,
            last_name="Point de Vente"
        )
        
        # Ajouter le groupe correspondant à l'emplacement
        group_name = POINT_VENTE_GROUP_MAPPING.get(self.emplacement, 'CAISSIER')
        try:
            group = Group.objects.get(name=group_name)
            user.groups.add(group)
        except Group.DoesNotExist:
            pass
        
        self.utilisateur = user
        self.save()
        return user
    
    
    
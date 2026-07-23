# apps/tresorerie/models/mouvement.py
from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from .caisse import Caisse


class MouvementCaisse(models.Model):
    TYPE_CHOICES = [
        ('ENTREE', 'Entrée'),
        ('SORTIE', 'Sortie'),
    ]

    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='mouvements')
    type_mouvement = models.CharField(max_length=20, choices=TYPE_CHOICES)
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    libelle = models.CharField(max_length=255)
    reference = models.CharField(max_length=100, blank=True, null=True)
    date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    # 🔥 Suivi des annulations
    annule = models.BooleanField(default=False)
    annule_le = models.DateTimeField(null=True, blank=True)
    annule_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='annulations')
    mouvement_parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True, related_name='annulations_liees')
    
    # 🔥 Source du mouvement
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    source = GenericForeignKey('content_type', 'object_id')

    class Meta:
        db_table = 'tresorerie_mouvements'
        verbose_name = 'Mouvement de caisse'
        verbose_name_plural = 'Mouvements de caisse'
        ordering = ['-date']

    def __str__(self):
        return f"{self.caisse.code} - {self.type_mouvement} - {self.montant:,.0f} F"
    
    
    
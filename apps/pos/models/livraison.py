from django.db import models
from .commande import Commande
from .livreur import Livreur

class Livraison(models.Model):
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('EN_COURS', 'En cours'),
        ('LIVREE', 'Livrée'),
        ('ANNULEE', 'Annulée'),
    ]

    commande = models.OneToOneField(Commande, on_delete=models.CASCADE, related_name='livraison')
    livreur = models.ForeignKey(Livreur, on_delete=models.SET_NULL, null=True, blank=True)
    nom_livreur = models.CharField(max_length=200, blank=True, help_text="Nom libre si livreur non sélectionné")
    adresse = models.TextField()
    frais = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    date_livraison = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pos_livraisons'
        verbose_name = 'Livraison'
        verbose_name_plural = 'Livraisons'

    def __str__(self):
        return f"Livraison {self.commande.numero} - {self.get_statut_display()}"

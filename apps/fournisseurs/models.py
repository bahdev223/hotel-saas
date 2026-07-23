import uuid
from django.db import models
from apps.comptabilite.models import CompteModel


def generate_id():
    return str(uuid.uuid4())[:8]


class Fournisseur(models.Model):
    id = models.CharField(max_length=50, primary_key=True, default=generate_id, editable=False)
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=200)
    telephone = models.CharField(max_length=20, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    adresse = models.TextField(blank=True, null=True)
    contact = models.CharField(max_length=100, blank=True, null=True)
    identifiant_fiscal = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    actif = models.BooleanField(default=True)
    compte_comptable = models.ForeignKey(
        CompteModel, on_delete=models.PROTECT,
        null=True, blank=True, related_name='fournisseurs_comptes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'stock_fournisseurs'
        verbose_name = 'Fournisseur'
        verbose_name_plural = 'Fournisseurs'
        ordering = ['nom']

    def __str__(self):
        return f"{self.code} - {self.nom}"

from django.db import models

class Livreur(models.Model):
    nom = models.CharField(max_length=200)
    telephone = models.CharField(max_length=50, blank=True)
    actif = models.BooleanField(default=True)

    class Meta:
        db_table = 'pos_livreurs'
        verbose_name = 'Livreur'
        verbose_name_plural = 'Livreurs'

    def __str__(self):
        return self.nom

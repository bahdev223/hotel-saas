from django.db import models


class CompteClient(models.Model):
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='comptes'
    )
    exercice = models.ForeignKey(
        'comptabilite.ExerciceModel',
        on_delete=models.CASCADE,
        related_name='comptes_clients'
    )
    solde = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ecart_lettrage = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compta_comptes_clients'
        verbose_name = 'Compte client'
        verbose_name_plural = 'Comptes clients'
        unique_together = ['client', 'exercice']

    def __str__(self):
        return f"{self.client.nom_complet} - {self.exercice.code}: {self.solde:,.0f} F"

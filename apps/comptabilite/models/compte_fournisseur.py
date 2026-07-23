from django.db import models


class CompteFournisseur(models.Model):
    fournisseur = models.ForeignKey(
        'fournisseurs.Fournisseur',
        on_delete=models.CASCADE,
        related_name='comptes'
    )
    exercice = models.ForeignKey(
        'comptabilite.ExerciceModel',
        on_delete=models.CASCADE,
        related_name='comptes_fournisseurs'
    )
    solde = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    ecart_lettrage = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'compta_comptes_fournisseurs'
        verbose_name = 'Compte fournisseur'
        verbose_name_plural = 'Comptes fournisseurs'
        unique_together = ['fournisseur', 'exercice']

    def __str__(self):
        return f"{self.fournisseur.nom} - {self.exercice.code}: {self.solde:,.0f} F"

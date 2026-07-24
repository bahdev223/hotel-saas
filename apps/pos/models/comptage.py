from django.db import models
from apps.rh.models import Employe
from decimal import Decimal


class ComptageSession(models.Model):
    session = models.OneToOneField('SessionCaisse', on_delete=models.PROTECT, related_name='comptage')

    especes_attendues = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    especes_comptees = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    ecart_especes = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    carte_attendue = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    carte_constatee = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    mobile_attendu = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    mobile_constate = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    cheque_attendu = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    cheque_constate = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    motif_ecart = models.TextField(blank=True)
    compte_par = models.ForeignKey(Employe, on_delete=models.PROTECT, related_name='comptages_effectues')
    compte_le = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Comptage de session"
        verbose_name_plural = "Comptages de session"

    def __str__(self):
        return f"Comptage session {self.session_id} — écart {self.ecart_especes}"

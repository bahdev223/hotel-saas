from django.db import models
from django.db.models import Sum, Q
from decimal import Decimal
from apps.tresorerie.models import Caisse
from apps.rh.models import Employe
from ..constants import StatutSession


class SessionCaisse(models.Model):
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='sessions_pos')
    point_vente = models.ForeignKey('PointVente', on_delete=models.CASCADE, related_name='sessions')
    shift = models.ForeignKey('ShiftEmploye', on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')

    ouverte_par = models.ForeignKey(
        Employe, on_delete=models.PROTECT, related_name='sessions_ouvertes',
    )
    fermee_par = models.ForeignKey(
        Employe, on_delete=models.PROTECT, null=True, blank=True, related_name='sessions_fermees',
    )
    validee_par = models.ForeignKey(
        Employe, on_delete=models.PROTECT, null=True, blank=True, related_name='sessions_validees',
    )

    date_ouverture = models.DateTimeField(auto_now_add=True)
    date_fermeture = models.DateTimeField(null=True, blank=True)

    solde_initial = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    statut = models.CharField(max_length=20, choices=StatutSession.choices, default=StatutSession.OUVERTE)

    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pos_sessions_caisse'
        verbose_name = 'Session de caisse'
        verbose_name_plural = 'Sessions de caisse'
        ordering = ['-date_ouverture']
        constraints = [
            models.UniqueConstraint(
                fields=['caisse'],
                condition=Q(statut__in=['OUVERTE', 'EN_COMPTAGE']),
                name='unique_session_active_par_caisse',
            ),
        ]

    def __str__(self):
        return f"Session {self.pk} - {self.ouverte_par} - {self.date_ouverture.strftime('%d/%m/%Y %H:%M')}"

    @property
    def total_especes(self):
        from .vente import Vente
        return Vente.objects.filter(session_caisse=self, statut='PAYEE', mode_paiement='ESPECES').aggregate(total=Sum('montant_total'))['total'] or 0

    @property
    def total_carte(self):
        from .vente import Vente
        return Vente.objects.filter(session_caisse=self, statut='PAYEE', mode_paiement='CARTE').aggregate(total=Sum('montant_total'))['total'] or 0

    @property
    def total_mobile_money(self):
        from .vente import Vente
        return Vente.objects.filter(session_caisse=self, statut='PAYEE', mode_paiement='MOBILE_MONEY').aggregate(total=Sum('montant_total'))['total'] or 0

    @property
    def total_ventes(self):
        from .vente import Vente
        return Vente.objects.filter(session_caisse=self, statut='PAYEE').aggregate(total=Sum('montant_total'))['total'] or 0

    @property
    def nombre_ventes(self):
        from .vente import Vente
        return Vente.objects.filter(session_caisse=self, statut='PAYEE').count()

    @property
    def duree(self):
        if self.date_fermeture:
            return (self.date_fermeture - self.date_ouverture).total_seconds() / 3600
        return 0

# apps/tresorerie/models/caisse.py
from django.db import models
from django.db.models import Q
from apps.comptabilite.models import CompteModel


class Caisse(models.Model):
    TYPE_FINANCIER_CHOICES = [
        ('ESPECES', 'Espèces'),
        ('BANQUE', 'Compte bancaire'),
        ('MOBILE_MONEY', 'Monnaie électronique'),
    ]

    ROLE_CHOICES = [
        ('CENTRALE', 'Caisse centrale'),
        ('POINT_VENTE', 'Point de vente'),
        ('GUICHET', 'Guichet'),
    ]

    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    type_financier = models.CharField(max_length=20, choices=TYPE_FINANCIER_CHOICES, default='ESPECES')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, null=True, blank=True)
    solde = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    actif = models.BooleanField(default=True)

    caisse_centrale = models.ForeignKey(
        'self', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='caisses_secondaires',
        help_text="Caisse centrale où déposer les excédents"
    )

    point_vente = models.ForeignKey(
        'pos.PointVente', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='caisses', help_text="Point de vente associé"
    )

    compte_comptable = models.ForeignKey(
        CompteModel, on_delete=models.PROTECT,
        limit_choices_to=Q(code__startswith='57') | Q(code__startswith='52') | Q(code__startswith='581'),
        help_text="Compte comptable associé",
        null=True, blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def est_centrale(self):
        return self.role == 'CENTRALE'

    @property
    def est_point_vente(self):
        return self.role == 'POINT_VENTE'

    @property
    def est_guichet(self):
        return self.role == 'GUICHET'

    @property
    def est_caisse(self):
        return self.type_financier == 'ESPECES'

    @property
    def est_banque(self):
        return self.type_financier == 'BANQUE'

    @property
    def est_mobile_money(self):
        return self.type_financier == 'MOBILE_MONEY'

    class Meta:
        db_table = 'tresorerie_caisses'
        verbose_name = 'Compte financier'
        verbose_name_plural = 'Comptes financiers'
        ordering = ['code']

    def __str__(self):
        if self.role:
            return f"{self.code} - {self.nom} ({self.get_type_financier_display()} - {self.get_role_display()})"
        return f"{self.code} - {self.nom} ({self.get_type_financier_display()})"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.compte_comptable:
            code = self.compte_comptable.code
            if self.type_financier == 'ESPECES' and not code.startswith('57'):
                raise ValidationError("Une caisse espèces doit être liée à un compte 57")
            if self.type_financier == 'BANQUE' and not code.startswith('52'):
                raise ValidationError("Un compte bancaire doit être lié à un compte 52")
            if self.type_financier == 'MOBILE_MONEY' and not code.startswith('581'):
                raise ValidationError("Un compte mobile money doit être lié à un compte 581")

            if Caisse.objects.filter(
                compte_comptable=self.compte_comptable
            ).exclude(pk=self.pk).exists():
                raise ValidationError(
                    f"Le compte comptable {self.compte_comptable.code} est déjà attribué "
                    f"à un autre compte financier"
                )

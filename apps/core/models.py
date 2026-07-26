from django.db import models
from django.utils import timezone
from apps.rh.models import Employe

class JourneeExploitation(models.Model):
    """
    La Journée d'Exploitation (Date Métier).
    Permet de découpler la date d'opération (ex: Vente à 02h du matin) 
    de la date civile, essentiel en hôtellerie.
    """
    STATUT_CHOICES = [
        ('OUVERTE', 'Ouverte'),
        ('FERMEE', 'Fermée'),
        ('CLOTUREE', 'Clôturée (Audit validé)'),
    ]

    date_metier = models.DateField(unique=True, help_text="La date logique de cette journée d'exploitation")
    
    date_ouverture = models.DateTimeField(auto_now_add=True)
    date_fermeture = models.DateTimeField(null=True, blank=True)
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='OUVERTE')
    
    ouverte_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, related_name='journees_ouvertes')
    fermee_par = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, blank=True, related_name='journees_fermees')

    class Meta:
        db_table = 'core_journee_exploitation'
        verbose_name = "Journée d'exploitation"
        verbose_name_plural = "Journées d'exploitation"
        ordering = ['-date_metier']

    def __str__(self):
        return f"Journée du {self.date_metier.strftime('%d/%m/%Y')} - {self.get_statut_display()}"

    @classmethod
    def get_journee_en_cours(cls):
        """Retourne la journée d'exploitation ouverte du jour, la crée si absente."""
        aujourdhui = timezone.localdate()
        journee, _ = cls.objects.get_or_create(
            date_metier=aujourdhui,
            defaults={'statut': 'OUVERTE'},
        )
        return journee

    def fermer(self, employe):
        self.statut = 'FERMEE'
        self.date_fermeture = timezone.now()
        self.fermee_par = employe
        self.save()


class IntegrationError(models.Model):
    """
    Enregistre une erreur d'intégration entre modules (compta, stock, etc.)
    sans bloquer le flux métier principal.
    """

    STATUS_CHOICES = [
        ('OPEN', 'Ouvert'),
        ('RETRYING', 'Nouvelle tentative'),
        ('RESOLVED', 'Résolu'),
        ('IGNORED', 'Ignoré'),
    ]

    module = models.CharField(max_length=50, help_text="Module source (ex: VENTE, STOCK, PAIEMENT)")
    operation = models.CharField(max_length=50, help_text="Opération (ex: COMPTABILISATION, CONSOMMATION)")
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=50, null=True, blank=True)
    message = models.TextField()
    details = models.TextField(blank=True)
    traceback = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='OPEN')
    attempt_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'core_integration_errors'
        verbose_name = 'Erreur d\'intégration'
        verbose_name_plural = 'Erreurs d\'intégration'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['module']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        return f"[{self.module}] {self.operation} — {self.status}"

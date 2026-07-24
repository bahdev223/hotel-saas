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

    def fermer(self, employe):
        self.statut = 'FERMEE'
        self.date_fermeture = timezone.now()
        self.fermee_par = employe
        self.save()

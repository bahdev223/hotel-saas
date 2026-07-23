# apps/comptabilite/models/configuration.py
from django.db import models
from decimal import Decimal
from datetime import date


class ConfigurationEntreprise(models.Model):
    """Configuration globale de l'entreprise"""
    
    # Informations générales
    nom = models.CharField(max_length=200, default="Mon Entreprise")
    logo = models.ImageField(upload_to='logos/', null=True, blank=True)
    
    # Adresse
    adresse = models.TextField(blank=True, null=True)
    telephone = models.CharField(max_length=50, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    site_web = models.URLField(blank=True, null=True)
    
    # Identifiants fiscaux
    nif = models.CharField(max_length=50, blank=True, null=True, help_text="Numéro d'Identification Fiscale")
    stat = models.CharField(max_length=50, blank=True, null=True, help_text="Numéro Statistique")
    rccm = models.CharField(max_length=50, blank=True, null=True, help_text="Registre de Commerce")
    
    # Devise
    devise = models.CharField(max_length=10, default="FCFA")
    
    # Exercice comptable
    exercice_annee = models.CharField(max_length=10, blank=True, null=True)
    exercice = models.ForeignKey('ExerciceModel', on_delete=models.SET_NULL, null=True, blank=True)
    
    # Statut d'initialisation
    est_initialise = models.BooleanField(default=False)
    date_initialisation = models.DateField(null=True, blank=True)
    nombre_comptes = models.IntegerField(default=0)

    # Assistant de mise en service
    situation_initiale_validee = models.BooleanField(default=False)
    date_validation_situation = models.DateTimeField(null=True, blank=True)
    contrepartie_situation = models.CharField(max_length=20, default='101')
    mode_demarrage = models.BooleanField(default=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compta_configuration_entreprise'
        verbose_name = 'Configuration entreprise'
        verbose_name_plural = 'Configurations entreprise'
    
    def __str__(self):
        return self.nom


class SoldesInitiaux(models.Model):
    """Soldes initiaux pour l'initialisation comptable"""
    
    configuration = models.OneToOneField(
        ConfigurationEntreprise, 
        on_delete=models.CASCADE,
        related_name='soldes_initiaux'
    )
    
    # Comptes de bilan
    caisse = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    banque = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    stocks = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    clients = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    fournisseurs = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Capital
    capital_social = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    capital_reel = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Réserves
    reserves = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    report_a_nouveau = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    
    # Dates
    date_creation = models.DateTimeField(auto_now_add=True)
    date_modification = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compta_soldes_initiaux'
        verbose_name = 'Soldes initiaux'
        verbose_name_plural = 'Soldes initiaux'
    
    def __str__(self):
        return f"Soldes initiaux - {self.configuration.nom}"


class ParametreEntreprise(models.Model):
    """Paramètres généraux de l'entreprise"""
    
    MODE_PAIE_CHOICES = [
        ('SIMPLE', 'Mode simple'),
        ('AVANCEE', 'Mode avancé'),
    ]
    
    entreprise = models.OneToOneField(
        ConfigurationEntreprise,
        on_delete=models.CASCADE,
        related_name='parametres'
    )
    
    # Paramètres de paie
    mode_paie = models.CharField(max_length=20, choices=MODE_PAIE_CHOICES, default='SIMPLE')
    gerer_cnps = models.BooleanField(default=False)
    gerer_impots = models.BooleanField(default=False)
    gerer_avances = models.BooleanField(default=True)
    
    # Paramètres de stock
    gerer_stock = models.BooleanField(default=True)
    methode_inventaire = models.CharField(max_length=20, choices=[('FIFO', 'FIFO'), ('LIFO', 'LIFO'), ('PMP', 'PMP')], default='FIFO')
    compte_contrepartie_stock = models.CharField(max_length=20, default='109', help_text="Compte comptable de contrepartie pour l'initialisation du stock (109 = situation initiale par défaut)")
    
    # Paramètres de facturation
    gerer_tva = models.BooleanField(default=True)
    taux_tva = models.DecimalField(max_digits=5, decimal_places=2, default=18.0)
    
    # Paramètres de trésorerie
    seuil_alerte_caisse = models.DecimalField(max_digits=10, decimal_places=2, default=50000)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'compta_parametres_entreprise'
        verbose_name = 'Paramètres entreprise'
        verbose_name_plural = 'Paramètres entreprise'
    
    @classmethod
    def get_compte_contrepartie(cls):
        obj = cls.objects.first()
        return obj.compte_contrepartie_stock if obj else '109'

    def __str__(self):
        return f"Paramètres - {self.entreprise.nom}"
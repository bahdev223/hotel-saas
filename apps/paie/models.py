import uuid
from decimal import Decimal
from django.db import models
from apps.rh.models import Employe, Contrat


def generate_id():
    """Génère un ID unique"""
    return str(uuid.uuid4())[:8]


class PeriodePaie(models.Model):
    """Période de paie (mois)"""
    annee = models.IntegerField()
    mois = models.IntegerField()
    date_debut = models.DateField()
    date_fin = models.DateField()
    cloture = models.BooleanField(default=False)
    date_cloture = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        unique_together = ['annee', 'mois']
        ordering = ['-annee', '-mois']
    
    def __str__(self):
        return f"{self.mois:02d}/{self.annee}"
    
    @property
    def libelle(self):
        mois_noms = ['', 'Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin', 
                     'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre']
        return f"{mois_noms[self.mois]} {self.annee}"


class RubriquePaie(models.Model):
    """Rubrique de paie"""
    TYPE_CHOICES = [
        ('BASE', 'Salaire de base'),
        ('PRIME', 'Prime'),
        ('AVANTAGE', 'Avantage'),
        ('RETENUE', 'Retenue'),
        ('COTISATION', 'Cotisation'),
        ('IMPOT', 'Impôt'),
    ]
    
    SENS_CHOICES = [
        ('BRUT', 'Ajout (brut)'),
        ('NET', 'Déduction (net)'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    libelle = models.CharField(max_length=100)
    type_rubrique = models.CharField(max_length=20, choices=TYPE_CHOICES)
    sens = models.CharField(max_length=10, choices=SENS_CHOICES, default='BRUT')
    taux = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    montant_fixe = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    actif = models.BooleanField(default=True)
    ordre = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['ordre', 'code']
    
    def __str__(self):
        return f"{self.code} - {self.libelle}"


class BulletinPaie(models.Model):
    """Bulletin de paie"""
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('CALCULE', 'Calculé'),
        ('VALIDE', 'Validé'),
        ('EDITE', 'Édité'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, default=generate_id, editable=False)  # ← CHANGÉ ICI
    numero = models.CharField(max_length=50, unique=True)
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='bulletins')
    periode = models.ForeignKey(PeriodePaie, on_delete=models.CASCADE, related_name='bulletins')
    contrat = models.ForeignKey(Contrat, on_delete=models.CASCADE, null=True, blank=True)
    
    base_calcul = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_brut = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_cotisations = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_impots = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    net_a_payer = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    date_calcul = models.DateTimeField(auto_now_add=True)
    date_validation = models.DateTimeField(null=True, blank=True)
    
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        unique_together = ['employe', 'periode']
        ordering = ['-periode__annee', '-periode__mois']
    
    def __str__(self):
        return f"Bulletin #{self.numero} - {self.employe.nom} {self.employe.prenom}"


class LigneBulletinPaie(models.Model):
    """Ligne détaillée du bulletin"""
    bulletin = models.ForeignKey(BulletinPaie, on_delete=models.CASCADE, related_name='lignes')
    rubrique = models.ForeignKey(RubriquePaie, on_delete=models.CASCADE)
    base = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    taux = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    montant = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    ordre = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['ordre']
    
    def __str__(self):
        return f"{self.rubrique.libelle} - {self.montant} FCFA"
    
    
class AvanceSalaire(models.Model):
    """Avance sur salaire demandée par un employé"""
    
    STATUT_CHOICES = [
        ('EN_ATTENTE', 'En attente'),
        ('APPROUVEE', 'Approuvée'),
        ('PAYEE', 'Payée'),
        ('REJETEE', 'Rejetée'),
        ('REMBOURSEE', 'Remboursée'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True, default=generate_id)
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='avances')
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    motif = models.CharField(max_length=200)
    date_demande = models.DateField(auto_now_add=True)
    date_approbation = models.DateField(null=True, blank=True)
    date_paiement = models.DateField(null=True, blank=True)
    mois_remboursement = models.IntegerField(help_text="Mois de remboursement (1-12)")
    annee_remboursement = models.IntegerField(help_text="Année de remboursement")
    nombre_mois = models.IntegerField(default=1, help_text="Nombre de mois d'étalement")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='EN_ATTENTE')
    approuve_par = models.CharField(max_length=100, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'paie_avances'
        ordering = ['-date_demande']
    
    def __str__(self):
        return f"Avance {self.employe.nom} - {self.montant} FCFA"
    
    @property
    def mensualite(self):
        """Montant à déduire par mois"""
        if self.nombre_mois > 0:
            return self.montant / self.nombre_mois
        return self.montant


class LigneRemboursement(models.Model):
    """Ligne de remboursement mensuel d'une avance"""
    
    avance = models.ForeignKey(AvanceSalaire, on_delete=models.CASCADE, related_name='remboursements')
    bulletin = models.ForeignKey(BulletinPaie, on_delete=models.CASCADE, null=True, blank=True, related_name='remboursements')
    mois = models.IntegerField()
    annee = models.IntegerField()
    montant = models.DecimalField(max_digits=10, decimal_places=2)
    rembourse = models.BooleanField(default=False)
    date_remboursement = models.DateField(null=True, blank=True)
    
    class Meta:
        db_table = 'paie_lignes_remboursement'
        unique_together = ['avance', 'mois', 'annee']
    
    def __str__(self):
        return f"Remboursement {self.avance.employe.nom} - {self.mois}/{self.annee} - {self.montant} FCFA"
    
    
    
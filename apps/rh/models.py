#hotel_project\apps\rh\models.py
"""
Modèles Django pour la gestion RH
"""

from django.db import models
from django.contrib.auth.models import User
from datetime import date

class Departement(models.Model):
    """Département de l'entreprise"""
    code = models.CharField(max_length=10, unique=True)
    libelle = models.CharField(max_length=100)
    responsable = models.ForeignKey('Employe', on_delete=models.SET_NULL, null=True, blank=True, related_name='departements_diriges')
    actif = models.BooleanField(default=True)
    
    class Meta:
        db_table = 'rh_departements'
    
    def __str__(self):
        return f"{self.code} - {self.libelle}"


class Poste(models.Model):
    """Poste de travail"""
    CLASSIFICATION_CHOICES = [
        ('Ouvrier', 'Ouvrier'),
        ('Employe', 'Employé'),
        ('Technicien', 'Technicien'),
        ('AgentMaitrise', 'Agent de maîtrise'),
        ('Cadre', 'Cadre'),
    ]
    
    code = models.CharField(max_length=10, unique=True)
    intitule = models.CharField(max_length=100)
    classification = models.CharField(max_length=20, choices=CLASSIFICATION_CHOICES)
    coefficient = models.IntegerField(null=True, blank=True)
    niveau = models.CharField(max_length=10, null=True, blank=True)
    salaire_base = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    class Meta:
        db_table = 'rh_postes'
    
    def __str__(self):
        return f"{self.code} - {self.intitule}"


class Employe(models.Model):
    """Employé (version Django DB)"""
    
    SITUATION_CHOICES = [
        ('Celibataire', 'Célibataire'),
        ('Marie', 'Marié(e)'),
        ('Pacse', 'Pacsé(e)'),
        ('Divorce', 'Divorcé(e)'),
        ('Veuf', 'Veuf/Veuve'),
    ]
    
    
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]
    
    # Lien avec User Django (authentification)
    user = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='employe')
    
    # Identité
    matricule = models.CharField(max_length=20, unique=True, blank=True)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100)
    date_naissance = models.DateField(null=True, blank=True)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, default='M')
    email = models.EmailField(null=True, blank=True)
    telephone = models.CharField(max_length=20, null=True, blank=True)
    adresse = models.TextField(null=True, blank=True)
    
    # Professionnel
    date_embauche = models.DateField(null=True, blank=True)
    departement = models.ForeignKey(Departement, on_delete=models.SET_NULL, null=True, blank=True, related_name='employes')
    poste = models.ForeignKey(Poste, on_delete=models.SET_NULL, null=True, blank=True, related_name='employes')
    # point_vente supprimé — déplacé vers AffectationPointVente + ShiftEmploye
    
    # Situation familiale
    situation_familiale = models.CharField(max_length=20, choices=SITUATION_CHOICES, default='Celibataire')
    nombre_enfants = models.IntegerField(default=0)
    
    # Conjoint(e)
    CIVILITE_CHOICES = [
        ('M.', 'M.'),
        ('Mme', 'Mme'),
    ]
    conjoint_civilite = models.CharField(max_length=5, choices=CIVILITE_CHOICES, blank=True, default='', verbose_name='Civilité du conjoint')
    conjoint_nom = models.CharField(max_length=100, blank=True, default='', verbose_name='Nom du conjoint')
    conjoint_prenom = models.CharField(max_length=100, blank=True, default='', verbose_name='Prénom du conjoint')
    conjoint_contact = models.CharField(max_length=20, blank=True, default='', verbose_name='Contact du conjoint')
    
    # Personne de référence
    personne_reference_nom = models.CharField(max_length=100, blank=True, default='', verbose_name='Nom de la personne de référence')
    personne_reference_prenom = models.CharField(max_length=100, blank=True, default='', verbose_name='Prénom de la personne de référence')
    personne_reference_contact = models.CharField(max_length=20, blank=True, default='', verbose_name='Contact de la personne de référence')
    
    # Salaire
    salaire_fixe = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text='Salaire mensuel fixe')
    
    # Photo
    photo = models.ImageField(upload_to='employes/', blank=True, null=True, verbose_name='Photo')

    # Diplôme
    diplome = models.CharField(max_length=200, blank=True, default='', verbose_name='Diplôme / Niveau d\'études')
    
    # Description
    description = models.TextField(blank=True, default='', verbose_name='Description')
    
    # Statut
    actif = models.BooleanField(default=True)
    date_sortie = models.DateField(null=True, blank=True)
    
    # Audit
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'rh_employes'
    
    def __str__(self):
        return f"{self.matricule} - {self.nom} {self.prenom}"
    
    @classmethod
    def generer_prochain_matricule(cls):
        annee = date.today().year
        prefix = f"RD-{annee}-"
        dernier = cls.objects.filter(matricule__startswith=prefix).order_by('matricule').last()
        if dernier and dernier.matricule:
            try:
                num = int(dernier.matricule.rsplit('-', 1)[-1]) + 1
            except (ValueError, IndexError):
                num = 1
        else:
            num = 1
        return f"{prefix}{num:04d}"
    
    def save(self, *args, **kwargs):
        if not self.matricule:
            self.matricule = Employe.generer_prochain_matricule()
        super().save(*args, **kwargs)
    
    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"
    
    @property
    def anciennete_annees(self):
        """Calcule l'ancienneté en années"""
        if not self.date_embauche:
            return 0
        delta = date.today() - self.date_embauche
        return delta.days / 365.25
    
    @property
    def age(self):
        """Calcule l'âge"""
        today = date.today()
        return today.year - self.date_naissance.year - (
            (today.month, today.day) < (self.date_naissance.month, self.date_naissance.day)
        )


class Contrat(models.Model):
    """Contrat de travail"""
    
    TYPE_CHOICES = [
        ('CDI', 'CDI'),
        ('CDD', 'CDD'),
        ('Stage', 'Stage'),
        ('Interim', 'Intérim'),
    ]
    
    id_contrat = models.CharField(max_length=20, unique=True)
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='contrats')
    type_contrat = models.CharField(max_length=20, choices=TYPE_CHOICES)
    date_debut = models.DateField()
    date_fin = models.DateField(null=True, blank=True)
    duree_heures_mois = models.DecimalField(max_digits=6, decimal_places=2, default=151.67)
    salaire_brut_mensuel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    statut_cadre = models.BooleanField(default=False)
    actif = models.BooleanField(default=True)
    commentaire = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'rh_contrats'
    
    def __str__(self):
        return f"{self.type_contrat} - {self.employe.matricule}"


class Conge(models.Model):
    """Demande de congé"""
    
    STATUT_CHOICES = [
        ('En attente', 'En attente'),
        ('Validé', 'Validé'),
        ('Refusé', 'Refusé'),
        ('Annulé', 'Annulé'),
    ]
    
    id_conge = models.CharField(max_length=20, unique=True)
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='conges')
    date_demande = models.DateField(auto_now_add=True)
    date_debut = models.DateField()
    date_fin = models.DateField()
    nb_jours_ouvrables = models.IntegerField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='En attente')
    commentaire = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'rh_conges'
    
    def __str__(self):
        return f"Congé {self.employe.matricule} - {self.date_debut}"


class Absence(models.Model):
    """Absence (maladie, etc.)"""
    
    TYPE_CHOICES = [
        ('Maladie', 'Maladie'),
        ('Accident travail', 'Accident de travail'),
        ('Maternite', 'Maternité'),
        ('Sans solde', 'Sans solde'),
        ('Formation', 'Formation'),
    ]
    
    id_absence = models.CharField(max_length=20, unique=True)
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='absences')
    date_debut = models.DateField()
    date_fin = models.DateField()
    type_absence = models.CharField(max_length=20, choices=TYPE_CHOICES)
    justificatif = models.FileField(upload_to='justificatifs/', null=True, blank=True)
    validee = models.BooleanField(default=False)
    commentaire = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'rh_absences'
    
    @property
    def nb_jours(self):
        delta = self.date_fin - self.date_debut
        return delta.days + 1


class Pointage(models.Model):
    """Pointage journalier"""
    
    id_pointage = models.CharField(max_length=20, unique=True)
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='pointages')
    date_pointage = models.DateField()
    heure_entree = models.TimeField(null=True, blank=True)
    heure_sortie = models.TimeField(null=True, blank=True)
    pause_dejeuner = models.DecimalField(max_digits=4, decimal_places=2, default=1.0)
    est_justifie = models.BooleanField(default=False)
    commentaire = models.TextField(null=True, blank=True)
    
    class Meta:
        db_table = 'rh_pointages'
    
    @property
    def heures_travaillees(self):
        if not self.heure_entree or not self.heure_sortie:
            return 0
        from datetime import datetime, timedelta
        entree = datetime.combine(self.date_pointage, self.heure_entree)
        if self.heure_sortie > self.heure_entree:
            sortie = datetime.combine(self.date_pointage, self.heure_sortie)
        else:
            sortie = datetime.combine(self.date_pointage + timedelta(days=1), self.heure_sortie)
        delta = sortie - entree
        heures = delta.total_seconds() / 3600
        return max(0, heures - float(self.pause_dejeuner))
    
    
    
    
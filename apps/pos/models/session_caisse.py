# apps/pos/models/session_caisse.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from decimal import Decimal
from apps.tresorerie.models import Caisse, TransfertCaisse
from apps.rh.models import Employe


class SessionCaisse(models.Model):
    """Session d'ouverture/fermeture de caisse avec suivi caissier"""
    
    STATUT_CHOICES = [
        ('OUVERTE', 'Ouverte'),
        ('FERMEE', 'Fermée'),
        ('SUSPENDUE', 'Suspendue'),
        ('CLOTUREE', 'Clôturée'),
    ]
    
    # Liens
    caisse = models.ForeignKey(Caisse, on_delete=models.CASCADE, related_name='sessions_pos')
    point_vente = models.ForeignKey('PointVente', on_delete=models.CASCADE, null=True, blank=True, related_name='sessions')
    
    # Caissiers (employés RH)
    caissier_ouverture = models.ForeignKey(
        Employe, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sessions_ouvertes'
    )
    caissier_fermeture = models.ForeignKey(
        Employe, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='sessions_fermees'
    )
    
    # RAF validation
    ouvert_par_raf = models.BooleanField(default=False, help_text="Ouverte avec dépôt RAF depuis la centrale")
    ferme_par_raf = models.ForeignKey(
        Employe, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='sessions_fermees_raf',
        help_text="RAF qui a validé la collecte et fermeture"
    )
    transfert_caisse = models.ForeignKey(
        TransfertCaisse, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='session_source',
        help_text="Transfert généré à la collecte (PV → Centrale)"
    )
    fonds_collectes = models.BooleanField(default=False, help_text="Les fonds ont été transférés à la caisse centrale")
    date_collecte = models.DateTimeField(null=True, blank=True, help_text="Quand le RAF a collecté les fonds")
    solde_initial_raf = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                            help_text="Solde initial déclaré/modifié par le RAF après ouverture")
    
    # Horaires
    date_ouverture = models.DateTimeField(auto_now_add=True)
    date_fermeture = models.DateTimeField(null=True, blank=True)
    
    # Plage horaire prévue
    debut_prevu = models.TimeField(null=True, blank=True, help_text="Heure de début de service prévue")
    fin_prevu = models.TimeField(null=True, blank=True, help_text="Heure de fin de service prévue")
    
    # Soldes
    solde_initial = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    solde_attendu = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    solde_reel = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    difference = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Dépôt / retrait à la clôture
    depot = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                help_text="Montant déposé/retiré à la clôture")
    solde_restant = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                        help_text="Solde laissé dans la caisse après clôture")
    
    # Lien vers le planning (optionnel)
    planning = models.ForeignKey('SessionPlanning', on_delete=models.SET_NULL, null=True, blank=True, related_name='sessions')
    
    # Montants par mode de paiement (pour rapprochement)
    total_especes = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_carte = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_mobile_money = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_compte_client = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    
    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='OUVERTE')
    
    # Métadonnées
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'pos_sessions_caisse'
        verbose_name = 'Session de caisse'
        verbose_name_plural = 'Sessions de caisse'
        ordering = ['-date_ouverture']
    
    def __str__(self):
        caissier_nom = self.caissier_ouverture.nom_complet if self.caissier_ouverture else "Inconnu"
        return f"Session {self.id} - {caissier_nom} - {self.date_ouverture.strftime('%d/%m/%Y %H:%M')}"
    
    @property
    def duree(self):
        """Durée de la session en heures"""
        if self.date_fermeture:
            delta = self.date_fermeture - self.date_ouverture
            return delta.total_seconds() / 3600
        return 0
    
    @property
    def caissier_actuel(self):
        """Retourne le caissier actuel si session ouverte"""
        if self.statut == 'OUVERTE':
            return self.caissier_ouverture
        return None
    
    @property
    def total_ventes(self):
        """Total des ventes pendant cette session"""
        from .vente import Vente
        return Vente.objects.filter(
            session_caisse=self,
            statut='PAYEE'
        ).aggregate(total=models.Sum('montant_total'))['total'] or 0
    
    @property
    def nombre_ventes(self):
        """Nombre de ventes pendant cette session"""
        from .vente import Vente
        return Vente.objects.filter(
            session_caisse=self,
            statut='PAYEE'
        ).count()
    
    def calculer_solde_attendu(self):
        """Calcule le solde attendu = solde_initial + total_ventes"""
        self.solde_attendu = self.solde_initial + self.total_ventes
        self.save(update_fields=['solde_attendu'])
        return self.solde_attendu
    
    def fermer(self, solde_reel, caissier_fermeture, notes="", depot=None):
        """Fermer la session avec le solde réel compté et dépôt optionnel.
        depot = montant à déposer/retirer. solde_restant = ce qui reste dans la caisse.
        Par défaut, tout le solde_reel est considéré comme restant."""
        self.solde_reel = solde_reel
        self.caissier_fermeture = caissier_fermeture
        self.date_fermeture = timezone.now()
        self.difference = solde_reel - self.solde_attendu
        self.depot = depot if depot is not None else 0
        self.solde_restant = solde_reel - (depot if depot is not None else 0)
        self.statut = 'FERMEE'
        self.notes = notes
        self.save()
        
        # Mettre à jour le solde de la caisse avec le solde restant
        caisse = self.caisse
        caisse.solde = self.solde_restant
        caisse.save()
        
        return self.difference
    
    def suspendre(self):
        """Suspendre la session (pause, changement de caissier temporaire)"""
        self.statut = 'SUSPENDUE'
        self.save()
    
    def reprendre(self):
        """Reprendre une session suspendue"""
        self.statut = 'OUVERTE'
        self.save()


class ChangementCaissier(models.Model):
    """Historique des changements de caissier pendant une session"""
    
    session = models.ForeignKey(SessionCaisse, on_delete=models.CASCADE, related_name='changements')
    ancien_caissier = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, related_name='changements_sortie')
    nouveau_caissier = models.ForeignKey(Employe, on_delete=models.SET_NULL, null=True, related_name='changements_entree')
    date_changement = models.DateTimeField(auto_now_add=True)
    raison = models.CharField(max_length=200, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    class Meta:
        db_table = 'pos_changements_caissier'
        verbose_name = 'Changement de caissier'
        verbose_name_plural = 'Changements de caissier'
        ordering = ['-date_changement']
    
    def __str__(self):
        ancien = self.ancien_caissier.nom_complet if self.ancien_caissier else "Début"
        nouveau = self.nouveau_caissier.nom_complet if self.nouveau_caissier else "Fin"
        return f"{ancien} → {nouveau} le {self.date_changement.strftime('%d/%m/%Y %H:%M')}"


class SessionPlanning(models.Model):
    """Planning prévisionnel des sessions — assigne un employé à un point de vente sur un créneau"""

    STATUT_CHOICES = [
        ('PLANIFIE', 'Planifié'),
        ('CONFIRME', 'Confirmé'),
        ('ANNULE', 'Annulé'),
        ('EFFECTUE', 'Effectué'),
    ]

    point_vente = models.ForeignKey('PointVente', on_delete=models.CASCADE, related_name='plannings')
    employe = models.ForeignKey(Employe, on_delete=models.CASCADE, related_name='sessions_planifiees')
    date = models.DateField()
    heure_debut = models.TimeField()
    heure_fin = models.TimeField()
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='PLANIFIE')
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'pos_planning_sessions'
        verbose_name = 'Planning session'
        verbose_name_plural = 'Plannings sessions'
        ordering = ['date', 'heure_debut']

    def __str__(self):
        return f"{self.employe.nom_complet} - {self.point_vente.nom} {self.date} {self.heure_debut}-{self.heure_fin}"
    
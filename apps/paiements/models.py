# apps/paiements/models.py
from django.db import models
from django.db import transaction
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.utils import timezone
from apps.tresorerie.models import Caisse
from apps.tresorerie.services import MouvementService
from apps.clients.models import Client
import uuid


class Paiement(models.Model):
    MODE_CHOICES = [
        ('ESPECES', 'Espèces'),
        ('CARTE', 'Carte bancaire'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('VIREMENT', 'Virement'),
        ('CHEQUE', 'Chèque'),
        ('CREDIT', 'Crédit'),
        ('SOLDE', 'Solde client'),
    ]

    SENS_CHOICES = [
        ('ENTREE', 'Entrée (encaissement)'),
        ('SORTIE', 'Sortie (décaissement)'),
    ]

    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('VALIDE', 'Validé'),
        ('ANNULE', 'Annulé'),
        ('REMBOURSE', 'Remboursé'),
    ]

    TYPE_PAIEMENT_CHOICES = [
        ('VENTE', 'Vente'),
        ('ACHAT', 'Achat fournisseur'),
        ('SALAIRE', 'Salaire'),
        ('AVANCE', 'Avance salaire'),
        ('DEPOT', 'Dépôt client'),
        ('REMBOURSEMENT', 'Remboursement'),
        ('TRANSFERT', 'Transfert'),
        ('AUTRE', 'Autre'),
    ]

    reference = models.CharField(max_length=50, unique=True, blank=True)
    type_paiement = models.CharField(max_length=20, choices=TYPE_PAIEMENT_CHOICES, default='AUTRE')
    montant = models.DecimalField(max_digits=12, decimal_places=2)
    sens = models.CharField(max_length=20, choices=SENS_CHOICES, default='SORTIE')
    mode = models.CharField(max_length=20, choices=MODE_CHOICES)
    caisse = models.ForeignKey(Caisse, on_delete=models.PROTECT, related_name='paiements')
    date = models.DateTimeField(auto_now_add=True)
    
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=50, db_index=True, null=True, blank=True)
    objet = GenericForeignKey('content_type', 'object_id')

    client = models.ForeignKey(Client, on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements')
    
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='paiements')
    valide_par = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='paiements_valides')
    date_validation = models.DateTimeField(null=True, blank=True)
    
    # Comptabilité
    est_comptabilise = models.BooleanField(default=False)
    date_comptabilisation = models.DateTimeField(null=True, blank=True)
    piece_comptable_id = models.CharField(max_length=50, blank=True, null=True)
    
    notes = models.TextField(blank=True, null=True)
    reference_externe = models.CharField(max_length=100, blank=True, null=True)
    devise = models.CharField(max_length=10, default='XOF')
    taux_change = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'paiements'
        verbose_name = 'Paiement'
        verbose_name_plural = 'Paiements'
        ordering = ['-date']
        indexes = [
            models.Index(fields=['reference']),
            models.Index(fields=['content_type', 'object_id']),
            models.Index(fields=['date']),
            models.Index(fields=['statut']),
            models.Index(fields=['type_paiement']),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = uuid.uuid4().hex[:8].upper()
        super().save(*args, **kwargs)

    def __str__(self):
        sens_icon = "📥" if self.sens == 'ENTREE' else "📤"
        return f"{sens_icon} {self.reference} - {self.montant:,.0f} F - {self.get_mode_display()}"

    @property
    def est_valide(self):
        return self.statut == 'VALIDE'
    
    @property
    def est_annule(self):
        return self.statut == 'ANNULE'
    
    @property
    def est_brouillon(self):
        return self.statut == 'BROUILLON'
    
    @transaction.atomic
    def valider(self, user):
        """Valider le paiement et créer le mouvement de trésorerie (avec verrouillage)"""
        # 🔥 Verrouiller la ligne pour éviter les doubles validations
        paiement = Paiement.objects.select_for_update().get(pk=self.pk)
        
        if paiement.statut != 'BROUILLON':
            raise ValueError(f"Impossible de valider un paiement {paiement.get_statut_display()}")
        
        # Créer le mouvement de trésorerie
        if paiement.sens == 'ENTREE':
            mouvement = MouvementService.encaisser(
                caisse=paiement.caisse,
                montant=paiement.montant,
                libelle=f"Paiement {paiement.reference} - {paiement.get_type_paiement_display()}",
                user=user,
                reference=paiement.reference,
                source=paiement
            )
        else:
            mouvement = MouvementService.decaisser(
                caisse=paiement.caisse,
                montant=paiement.montant,
                libelle=f"Paiement {paiement.reference} - {paiement.get_type_paiement_display()}",
                user=user,
                reference=paiement.reference,
                source=paiement
            )
        
        paiement.statut = 'VALIDE'
        paiement.valide_par = user
        paiement.date_validation = timezone.now()  # 🔥 CORRIGÉ : use timezone.now()
        paiement.save()
        
        return mouvement
    
    @transaction.atomic
    def annuler(self, user, raison=""):
        """Annuler le paiement et créer un mouvement inverse (avec verrouillage)"""
        # 🔥 Verrouiller la ligne
        paiement = Paiement.objects.select_for_update().get(pk=self.pk)
        
        if paiement.statut == 'ANNULE':
            raise ValueError("Ce paiement est déjà annulé")
        
        if paiement.statut == 'VALIDE':
            # Récupérer les mouvements associés (peut être plusieurs)
            mouvements = paiement.mouvements.all()
            for mouvement in mouvements:
                if not mouvement.annule:
                    MouvementService.annuler_mouvement(mouvement, user, raison)
        
        paiement.statut = 'ANNULE'
        paiement.notes = f"{paiement.notes}\nANNULÉ le {timezone.now()} par {user} : {raison}" if paiement.notes else f"ANNULÉ par {user} : {raison}"
        paiement.save()
        
        return True
    
    @property
    def mouvements(self):
        """Récupérer TOUS les mouvements de trésorerie associés"""
        from django.contrib.contenttypes.models import ContentType
        from apps.tresorerie.models import MouvementCaisse
        
        content_type = ContentType.objects.get_for_model(self)
        return MouvementCaisse.objects.filter(
            content_type=content_type,
            object_id=self.pk
        )
    
    @property
    def mouvement_principal(self):
        """Récupérer le mouvement principal (premier mouvement)"""
        return self.mouvements.first()
    
    def marquer_comptabilise(self, piece_comptable_id=None):
        """Marquer le paiement comme comptabilisé"""
        self.est_comptabilise = True
        self.date_comptabilisation = timezone.now()
        if piece_comptable_id:
            self.piece_comptable_id = piece_comptable_id
        self.save()
        
        
        
        
        
        
        
        
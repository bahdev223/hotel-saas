from django.db import models
import uuid


def generate_unite_id():
    return f"U{uuid.uuid4().hex[:8].upper()}"


class StatutChambre(models.TextChoices):
    DISPONIBLE = "DISPONIBLE", "Disponible"
    RESERVEE = "RESERVEE", "Réservée"
    OCCUPEE = "OCCUPEE", "Occupée"
    A_NETTOYER = "A_NETTOYER", "À nettoyer"
    NETTOYAGE = "NETTOYAGE", "Nettoyage en cours"
    A_INSPECTER = "A_INSPECTER", "À inspecter"
    MAINTENANCE = "MAINTENANCE", "En maintenance"
    HORS_SERVICE = "HORS_SERVICE", "Hors service"


class UniteModel(models.Model):
    TYPE_CHOICES = [
        ('CHAMBRE', 'Chambre'),
        ('VIP', 'VIP'),
        ('SALLE', 'Salle'),
        ('ESPACE', 'Espace'),
        ('ESPACE_BAR', 'Espace + Bar'),
        ('BAR', 'Bar VIP'),
    ]

    STATUT_CHOICES = [(s.value, s.label) for s in StatutChambre]

    id = models.CharField(max_length=50, primary_key=True, default=generate_unite_id, editable=False)
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    type_unite = models.CharField(max_length=20, choices=TYPE_CHOICES, default='CHAMBRE')

    type_chambre = models.ForeignKey(
        "hotel.TypeChambre",
        on_delete=models.PROTECT,
        related_name="unites",
        null=True,
        blank=True,
    )

    capacite = models.IntegerField(default=1)
    surface_m2 = models.FloatField(null=True, blank=True)
    equipements = models.JSONField(default=list)
    prix = models.DecimalField(max_digits=10, decimal_places=2, help_text="Prix par heure")
    prix_jour = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Prix par jour")
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='DISPONIBLE')
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='hotel/unites/', null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'hotel_unites'
        verbose_name = 'Chambre'
        verbose_name_plural = 'Chambres'
        ordering = ['type_unite', 'code']

    def __str__(self):
        return f"{self.code} - {self.nom}"

    def occuper(self):
        self.statut = StatutChambre.OCCUPEE
        self.save(update_fields=["statut"])

    def liberer(self):
        self.statut = StatutChambre.A_NETTOYER
        self.save(update_fields=["statut"])

    def reserver(self):
        self.statut = StatutChambre.RESERVEE
        self.save(update_fields=["statut"])

    def mettre_a_nettoyer(self):
        self.statut = StatutChambre.A_NETTOYER
        self.save(update_fields=["statut"])

    def mettre_en_maintenance(self):
        self.statut = StatutChambre.MAINTENANCE
        self.save(update_fields=["statut"])
        
        
        
import uuid
from django.db import models


def generate_client_id():
    return f"C{uuid.uuid4().hex[:8].upper()}"


class Client(models.Model):
    TYPE_CLIENT_CHOICES = [
        ('PARTICULIER', 'Particulier'),
        ('ENTREPRISE', 'Entreprise'),
        ('AGENCE', 'Agence de voyage'),
    ]
    STATUT_CHOICES = [
        ('ACTIF', 'Actif'),
        ('INACTIF', 'Inactif'),
        ('BLACKLIST', 'Blacklisté'),
    ]
    SEXE_CHOICES = [
        ('M', 'Masculin'),
        ('F', 'Féminin'),
    ]

    id = models.CharField(max_length=50, primary_key=True, default=generate_client_id, editable=False)
    nom = models.CharField(max_length=100)
    prenom = models.CharField(max_length=100, blank=True, default='')
    email = models.EmailField(blank=True, null=True)
    telephone = models.CharField(max_length=20)
    adresse = models.TextField(blank=True, null=True)
    sexe = models.CharField(max_length=1, choices=SEXE_CHOICES, blank=True, null=True)
    date_naissance = models.DateField(null=True, blank=True)

    type_client = models.CharField(max_length=20, choices=TYPE_CLIENT_CHOICES, default='PARTICULIER')
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='ACTIF')

    piece_identite = models.CharField(max_length=50, blank=True, null=True)
    numero_piece = models.CharField(max_length=50, blank=True, null=True)
    identifiant_fiscal = models.CharField(max_length=50, blank=True, null=True)

    notes = models.TextField(blank=True, null=True)
    credit_plafond = models.DecimalField(max_digits=12, decimal_places=2, default=0, help_text='Plafond de crédit (0 = pas de limite)')

    date_inscription = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Passager singleton ID (known constant for "Client Passager")
    PASSAGER_ID = "C00000001"

    class Meta:
        db_table = 'clients_client'
        verbose_name = 'Client'
        verbose_name_plural = 'Clients'
        ordering = ['nom', 'prenom']
        indexes = [
            models.Index(fields=['nom']),
            models.Index(fields=['telephone']),
            models.Index(fields=['statut']),
        ]

    def __str__(self):
        return self.nom_complet

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}".strip()

    @staticmethod
    def get_passager():
        client, _ = Client.objects.get_or_create(
            id=Client.PASSAGER_ID,
            defaults={
                'nom': 'Client',
                'prenom': 'Passager',
                'telephone': '0000000000',
                'statut': 'ACTIF',
                'type_client': 'PARTICULIER',
            }
        )
        return client

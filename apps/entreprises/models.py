from django.db import models


class Entreprise(models.Model):
    class FormeJuridique(models.TextChoices):
        ENTREPRISE_INDIVIDUELLE = "EI", "Entreprise individuelle"
        SARL = "SARL", "SARL"
        SA = "SA", "SA"
        SAS = "SAS", "SAS"
        ASSOCIATION = "ASSOCIATION", "Association"
        AUTRE = "AUTRE", "Autre"

    nom = models.CharField(max_length=200)
    nom_commercial = models.CharField(max_length=200, blank=True)
    code = models.SlugField(max_length=100, unique=True)

    forme_juridique = models.CharField(
        max_length=20,
        choices=FormeJuridique.choices,
        blank=True,
    )

    nif = models.CharField(max_length=100, blank=True)
    rccm = models.CharField(max_length=100, blank=True)
    numero_statistique = models.CharField(max_length=100, blank=True)
    numero_art = models.CharField(max_length=100, blank=True, verbose_name="Numéro d'agrément ART")

    telephone = models.CharField(max_length=30, blank=True)
    telephone_secondaire = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    site_web = models.URLField(blank=True)

    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)
    pays = models.CharField(max_length=100, default="Mali")

    logo = models.ImageField(
        upload_to="entreprises/logos/",
        blank=True,
        null=True,
    )

    cachet = models.ImageField(
        upload_to="entreprises/cachets/",
        blank=True,
        null=True,
    )

    signature = models.ImageField(
        upload_to="entreprises/signatures/",
        blank=True,
        null=True,
    )

    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Entreprise"
        verbose_name_plural = "Entreprises"

    def __str__(self):
        return self.nom_commercial or self.nom


class Etablissement(models.Model):
    class TypeEtablissement(models.TextChoices):
        HOTEL = "HOTEL", "Hôtel"
        HOTEL_RESTAURANT = "HOTEL_RESTAURANT", "Hôtel-restaurant"
        RESIDENCE = "RESIDENCE", "Résidence"
        AUBERGE = "AUBERGE", "Auberge"
        COMPLEXE = "COMPLEXE", "Complexe hôtelier"
        MOTEL = "MOTEL", "Motel"
        AUTRE = "AUTRE", "Autre"

    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.PROTECT,
        related_name="etablissements",
    )

    nom = models.CharField(max_length=200)
    code = models.SlugField(max_length=100, unique=True)
    type_etablissement = models.CharField(
        max_length=30,
        choices=TypeEtablissement.choices,
        default=TypeEtablissement.HOTEL,
    )

    telephone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    adresse = models.TextField(blank=True)
    ville = models.CharField(max_length=100, blank=True)

    nombre_etoiles = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
    )

    actif = models.BooleanField(default=True)
    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Établissement"
        verbose_name_plural = "Établissements"

    def __str__(self):
        return self.nom


class ConfigurationEntreprise(models.Model):
    entreprise = models.OneToOneField(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="configuration",
    )

    devise = models.CharField(max_length=10, default="XOF")
    symbole_devise = models.CharField(max_length=10, default="FCFA")
    langue = models.CharField(max_length=10, default="fr")
    fuseau_horaire = models.CharField(
        max_length=100,
        default="Africa/Bamako",
    )

    format_date = models.CharField(
        max_length=30,
        default="d/m/Y",
    )

    exercice_comptable_debut_mois = models.PositiveSmallIntegerField(
        default=1,
    )

    couleur_principale = models.CharField(
        max_length=20,
        default="#1F2937",
    )

    couleur_secondaire = models.CharField(
        max_length=20,
        default="#D4AF37",
    )

    pied_facture = models.TextField(blank=True)
    conditions_facture = models.TextField(blank=True)

    configuration_terminee = models.BooleanField(default=False)

    cree_le = models.DateTimeField(auto_now_add=True)
    modifie_le = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuration de l'entreprise"
        verbose_name_plural = "Configurations de l'entreprise"

    def __str__(self):
        return f"Configuration de {self.entreprise}"


class ConfigurationHoteliere(models.Model):
    etablissement = models.OneToOneField(
        Etablissement,
        on_delete=models.CASCADE,
        related_name="configuration_hoteliere",
    )

    heure_check_in = models.TimeField(default="14:00")
    heure_check_out = models.TimeField(default="12:00")

    autoriser_arrivee_anticipee = models.BooleanField(default=True)
    autoriser_depart_tardif = models.BooleanField(default=True)

    pourcentage_acompte_reservation = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    delai_annulation_gratuite_heures = models.PositiveIntegerField(
        default=24,
    )

    liberation_automatique_chambre = models.BooleanField(default=False)
    passage_nettoyage_apres_depart = models.BooleanField(default=True)

    autoriser_surclassement = models.BooleanField(default=True)
    autoriser_changement_chambre = models.BooleanField(default=True)

    texte_confirmation_reservation = models.TextField(blank=True)
    politique_annulation = models.TextField(blank=True)

    class Meta:
        verbose_name = "Configuration hôtelière"
        verbose_name_plural = "Configurations hôtelières"

    def __str__(self):
        return f"Configuration hôtelière de {self.etablissement}"


class ModuleEntreprise(models.Model):
    class CodeModule(models.TextChoices):
        HOTEL = "HOTEL", "Hôtel"
        RESTAURANT = "RESTAURANT", "Restaurant"
        POS = "POS", "Points de vente"
        STOCK = "STOCK", "Stocks"
        FOURNISSEURS = "FOURNISSEURS", "Fournisseurs"
        FACTURATION = "FACTURATION", "Facturation"
        PAIEMENTS = "PAIEMENTS", "Paiements"
        TRESORERIE = "TRESORERIE", "Trésorerie"
        COMPTABILITE = "COMPTABILITE", "Comptabilité"
        RH = "RH", "Ressources humaines"
        PAIE = "PAIE", "Paie"

    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="modules",
    )

    code = models.CharField(
        max_length=30,
        choices=CodeModule.choices,
    )

    actif = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Module"
        verbose_name_plural = "Modules"
        constraints = [
            models.UniqueConstraint(
                fields=["entreprise", "code"],
                name="unique_module_par_entreprise",
            )
        ]

    def __str__(self):
        return f"{self.get_code_display()} - {'Actif' if self.actif else 'Inactif'}"


class SequenceDocument(models.Model):
    class TypeDocument(models.TextChoices):
        RESERVATION = "RESERVATION", "Réservation"
        SEJOUR = "SEJOUR", "Séjour"
        FACTURE = "FACTURE", "Facture"
        RECU = "RECU", "Reçu"
        AVOIR = "AVOIR", "Avoir"
        COMMANDE = "COMMANDE", "Commande"
        ACHAT = "ACHAT", "Achat"
        INVENTAIRE = "INVENTAIRE", "Inventaire"
        BON_LIVRAISON = "BON_LIVRAISON", "Bon de livraison"
        DEPENSE = "DEPENSE", "Dépense"
        TRANSFERT = "TRANSFERT", "Transfert"

    entreprise = models.ForeignKey(
        Entreprise,
        on_delete=models.CASCADE,
        related_name="sequences_documents",
    )

    type_document = models.CharField(
        max_length=30,
        choices=TypeDocument.choices,
    )

    prefixe = models.CharField(max_length=20)
    prochain_numero = models.PositiveBigIntegerField(default=1)
    longueur_numero = models.PositiveSmallIntegerField(default=6)
    reinitialisation_annuelle = models.BooleanField(default=True)
    annee = models.PositiveSmallIntegerField()

    class Meta:
        verbose_name = "Séquence de document"
        verbose_name_plural = "Séquences de documents"
        constraints = [
            models.UniqueConstraint(
                fields=["entreprise", "type_document", "annee"],
                name="unique_sequence_document_annee",
            )
        ]

    def __str__(self):
        return f"{self.prefixe}-{self.annee}-{self.prochain_numero:0{self.longueur_numero}d}"

    def prochain(self):
        return f"{self.prefixe}-{self.annee}-{self.prochain_numero:0{self.longueur_numero}d}"

    def incremente(self):
        self.prochain_numero += 1
        self.save(update_fields=["prochain_numero"])

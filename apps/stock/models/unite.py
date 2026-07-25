from django.db import models

class UniteMesure(models.Model):
    """Unité de mesure de base (Kg, L, Pièce, etc.)"""
    
    TYPE_UNITE_CHOICES = [
        ('MASSE', 'Masse (Kg, g...)'),
        ('VOLUME', 'Volume (L, cl...)'),
        ('UNITE', 'Unité (Pièce, Unité)'),
        ('LONGUEUR', 'Longueur (m, cm...)'),
    ]
    
    nom = models.CharField(max_length=50, unique=True, help_text="Ex: Kilogramme, Litre, Pièce")
    symbole = models.CharField(max_length=10, unique=True, help_text="Ex: kg, l, pce")
    type_unite = models.CharField(max_length=20, choices=TYPE_UNITE_CHOICES, default='UNITE')
    unite_reference = models.BooleanField(
        default=False, 
        help_text="Cocher si c'est l'unité de référence pour ce type (ex: Kg pour la Masse)"
    )
    actif = models.BooleanField(default=True)

    class Meta:
        db_table = 'stock_unite_mesure'
        verbose_name = 'Unité de mesure'
        verbose_name_plural = 'Unités de mesure'
        ordering = ['type_unite', 'nom']

    def __str__(self):
        return f"{self.nom} ({self.symbole})"

    @classmethod
    def get_or_create_by_symbole(cls, symbole, nom=None, type_unite='UNITE'):
        """Résout une UniteMesure à partir d'un symbole texte (ex: 'kg'), la crée si absente.
        Utilisé pour la compatibilité ascendante avec l'ancien champ texte Produit.unite_base."""
        if not symbole:
            return None
        return cls.objects.get_or_create(
            symbole=symbole,
            defaults={'nom': nom or symbole, 'type_unite': type_unite},
        )[0]


class ConversionUnite(models.Model):
    """Taux de conversion générique entre deux unités (ex: 1 Kg = 1000 g)"""
    
    unite_source = models.ForeignKey(UniteMesure, on_delete=models.CASCADE, related_name='conversions_source')
    unite_dest = models.ForeignKey(UniteMesure, on_delete=models.CASCADE, related_name='conversions_dest')
    facteur = models.DecimalField(
        max_digits=18, decimal_places=6,
        help_text="Quantité de destination obtenue pour 1 unité source. (ex: Source=Kg, Dest=g, Facteur=1000)"
    )
    
    class Meta:
        db_table = 'stock_conversion_unite'
        verbose_name = 'Conversion d\'unité'
        verbose_name_plural = 'Conversions d\'unités'
        unique_together = ['unite_source', 'unite_dest']
        
    def __str__(self):
        return f"1 {self.unite_source.symbole} = {self.facteur} {self.unite_dest.symbole}"

# apps/stock/models/produit.py
from django.db import models
from .categorie import CategorieProduit


class Produit(models.Model):
    """Produit unique dans l'entrepôt central"""
    
    TYPE_ARTICLE_CHOICES = [
        ('MARCHANDISE', 'Marchandise'),
        ('MATIERE_PREMIERE', 'Matière première'),
        ('EMBALLAGE', 'Emballage'),
        ('CONSOMMABLE', 'Consommable interne'),
        ('IMMOBILISATION', 'Immobilisation'),
        ('SERVICE', 'Service'),
    ]
    
    UNITE_CHOICES = [
        ('piece', 'Pièce'),
        ('kg', 'Kilogramme'),
        ('g', 'Gramme'),
        ('l', 'Litre'),
        ('cl', 'Centilitre'),
        ('botte', 'Botte'),
        ('sachet', 'Sachet'),
        ('boite', 'Boîte'),
        ('caisse', 'Caisse'),
    ]
    
    code = models.CharField(max_length=50, unique=True)
    code_barre = models.CharField(max_length=100, unique=True, blank=True, null=True, help_text="Code-barres EAN-13 / Code produit")
    nom = models.CharField(max_length=200)
    categorie = models.ForeignKey(CategorieProduit, on_delete=models.SET_NULL, null=True, blank=True)
    type_article = models.CharField(
        max_length=30,
        choices=TYPE_ARTICLE_CHOICES,
        default='MARCHANDISE'
    )
    est_vendable = models.BooleanField(default=False, verbose_name="Visible dans le catalogue")
    unite_base = models.CharField(max_length=20, choices=UNITE_CHOICES, default='piece')
    
    # Prix
    prix_achat = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    # Stock central
    seuil_alerte = models.DecimalField(max_digits=10, decimal_places=2, default=5)
    
    # Pour consommables
    budget_mensuel = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='stock/produits/', null=True, blank=True)
    domaine = models.ForeignKey('Domaine', on_delete=models.SET_NULL, null=True, blank=True)
    actif = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'stock_produits'
        verbose_name = 'Produit'
        verbose_name_plural = 'Produits'
        ordering = ['nom']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    @property
    def quantite_stock(self):
        """Stock total du produit dans tous les entrepôts"""
        return self.stocks_entrepots.aggregate(total=models.Sum('quantite'))['total'] or 0

    @property
    def valeur_stock(self):
        return float(self.quantite_stock) * float(self.prix_achat)
    
    @property
    def est_en_rupture(self):
        return self.quantite_stock <= 0
    
    @property
    def est_en_alerte(self):
        return 0 < self.quantite_stock <= self.seuil_alerte
    
    @property
    def stock_converti(self):
        """Retourne le stock formaté avec toutes les unités (intelligent)"""
        from decimal import Decimal
        
        if not self.sous_unites.exists():
            return f"{int(self.quantite_stock)} {self.unite_base}"
        
        result = []
        reste = int(self.quantite_stock)
        
        sous_unites_triees = self.sous_unites.filter(actif=True).order_by('-facteur')
        
        for su in sous_unites_triees:
            facteur = int(su.facteur)
            if facteur > 0 and reste >= facteur:
                nb = reste // facteur
                result.append(f"{nb} {su.nom}")
                reste = reste % facteur
        
        if reste > 0 or not result:
            result.append(f"{reste} {self.unite_base}")
        
        return ", ".join(result)
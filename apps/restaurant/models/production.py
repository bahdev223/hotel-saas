# apps/restaurant/models/production.py
from django.db import models
from django.utils import timezone
from decimal import Decimal
from .recette import RecetteModel
from apps.stock.models import Produit, StockEntrepot, Entrepot
from django.db import models, transaction

class Production(models.Model):
    """Production en cuisine - préparation de recettes"""
    
    STATUT_CHOICES = [
        ('BROUILLON', 'Brouillon'),
        ('EN_COURS', 'En cours'),
        ('TERMINE', 'Terminé'),
        ('VALIDE', 'Validé'),
        ('ANNULE', 'Annulé'),
    ]
    
    # Identification
    numero = models.CharField(max_length=20, unique=True, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    date_production = models.DateField(null=True, blank=True, help_text="Date prévue de production")
    
    # Responsables
    produit_par = models.ForeignKey(
        'rh.Employe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productions'
    )
    valide_par = models.ForeignKey(
        'rh.Employe',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='productions_validees'
    )
    
    # Liens entrepôts
    entrepot_source = models.ForeignKey(
        'stock.Entrepot',
        on_delete=models.SET_NULL,
        null=True,
        related_name='productions_sorties'
    )
    entrepot_dest = models.ForeignKey(
        'stock.Entrepot',
        on_delete=models.SET_NULL,
        null=True,
        related_name='productions_entrees'
    )
    
    # Statut
    statut = models.CharField(max_length=20, choices=STATUT_CHOICES, default='BROUILLON')
    
    # Métadonnées
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'restaurant_productions'
        verbose_name = 'Production'
        verbose_name_plural = 'Productions'
        ordering = ['-date']
    
    def save(self, *args, **kwargs):
        if not self.numero:
            import uuid
            self.numero = f"PRD-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Production #{self.numero} - {self.date.strftime('%d/%m/%Y')}"
    
    @property
    def total_unites(self):
        """Total des unités produites"""
        return sum(l.quantite for l in self.lignes.all())
    
    def verifier_stock(self):
        """Vérifie si tous les ingrédients sont disponibles"""
        from decimal import Decimal
        manques = []

        for ligne in self.lignes.select_related('recette').all():
            if not ligne.recette:
                manques.append(f"Ligne #{ligne.id}: aucune recette associée")
                continue

            for ingredient in ligne.recette.ingredients.filter(
                type_ingredient='DEDUIRE',
                produit__isnull=False
            ):
                if not ingredient.quantite:
                    continue

                quantite_necessaire = ingredient.quantite * ligne.quantite
                stock = StockEntrepot.objects.filter(
                    entrepot=self.entrepot_source,
                    produit=ingredient.produit
                ).first()

                stock_qte = stock.quantite if stock else Decimal('0')

                if stock_qte < quantite_necessaire:
                    manques.append(
                        f"{ingredient.produit.nom}: besoin {quantite_necessaire} {ingredient.unite}, "
                        f"disponible {stock_qte}"
                    )

        return {'disponible': len(manques) == 0, 'manques': manques}
    
    @transaction.atomic
    def valider(self, employe):
        """Valide la production : sortie ingrédients + entrée produit fini"""
        from apps.stock.services.mouvement_service import MouvementStockService

        if self.statut == 'VALIDE':
            raise ValueError("Cette production a déjà été validée")

        if not self.entrepot_source:
            raise ValueError("Entrepôt source non défini")
        if not self.entrepot_dest:
            raise ValueError("Entrepôt destination non défini")

        # Vérifier le stock
        verification = self.verifier_stock()
        if not verification['disponible']:
            raise ValueError(f"Stock insuffisant: {', '.join(verification['manques'])}")

        # Appliquer les modifications
        for ligne in self.lignes.select_related('recette', 'recette__produit_fini').all():
            if not ligne.recette:
                continue

            # Sortie des ingrédients
            for ingredient in ligne.recette.ingredients.filter(
                type_ingredient='DEDUIRE',
                produit__isnull=False
            ):
                if not ingredient.quantite:
                    continue

                quantite_necessaire = ingredient.quantite * ligne.quantite

                MouvementStockService.sortie_stock(
                    produit=ingredient.produit,
                    entrepot=self.entrepot_source,
                    quantite=quantite_necessaire,
                    utilisateur=str(employe) if employe else "Cuisine",
                    motif='consommation',
                    raison=f"Production #{self.numero}: {ligne.recette.nom}",
                )

                ProductionIngredient.objects.create(
                    production=self,
                    produit=ingredient.produit,
                    quantite=quantite_necessaire,
                    unite=ingredient.unite
                )

            # Entrée du produit fini dans l'entrepôt destination
            if ligne.recette.produit_fini:
                quantite_produite = ligne.quantite
                if ligne.recette.rendement_quantite:
                    quantite_produite = quantite_produite * ligne.recette.rendement_quantite

                MouvementStockService.entree_stock(
                    produit=ligne.recette.produit_fini,
                    entrepot=self.entrepot_dest,
                    quantite=quantite_produite,
                    utilisateur=str(employe) if employe else "Cuisine",
                    motif='production',
                    raison=f"Production #{self.numero}: {ligne.recette.nom}",
                )

        self.statut = 'VALIDE'
        self.valide_par = employe
        self.save()

        return True
    
    @transaction.atomic
    def annuler(self):
        """Annule la production (si non validée)"""
        if self.statut == 'VALIDE':
            raise ValueError("Impossible d'annuler une production validée")
        
        self.statut = 'ANNULE'
        self.save()


class ProductionLigne(models.Model):
    """Ligne de production - une recette produite"""
    
    production = models.ForeignKey(
        Production,
        on_delete=models.CASCADE,
        related_name='lignes'
    )
    recette = models.ForeignKey(
        RecetteModel,
        on_delete=models.CASCADE,
        related_name='productions'
    )
    quantite = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=1
    )
    
    class Meta:
        db_table = 'restaurant_production_lignes'
        verbose_name = 'Ligne de production'
        verbose_name_plural = 'Lignes de production'
    
    def __str__(self):
        return f"{self.quantite} x {self.recette.nom}"


class ProductionIngredient(models.Model):
    """Ingrédients consommés pour une production"""
    
    production = models.ForeignKey(
        Production,
        on_delete=models.CASCADE,
        related_name='ingredients'
    )
    produit = models.ForeignKey(
        Produit,
        on_delete=models.CASCADE
    )
    quantite = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )
    unite = models.CharField(max_length=20, blank=True, null=True)
    
    class Meta:
        db_table = 'restaurant_production_ingredients'
        verbose_name = 'Ingrédient consommé'
        verbose_name_plural = 'Ingrédients consommés'
    
    def __str__(self):
        return f"{self.quantite} x {self.produit.nom}"
    
    
    
    
    
    
# apps/restaurant/models/menu.py
from django.db import models
from .recette import RecetteModel


class MenuModel(models.Model):
    """Menu commercial vendu au client"""
    
    TYPE_MENU_CHOICES = [
        ('FASTFOOD', 'Fast-food'),
        ('PLAT', 'Plat'),
    ]
    
    code = models.CharField(max_length=20, unique=True)
    nom = models.CharField(max_length=100)
    type_menu = models.CharField(max_length=20, choices=TYPE_MENU_CHOICES, default='PLAT')
    prix_vente = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    
    description = models.TextField(blank=True, null=True)
    image = models.ImageField(upload_to='menus/', blank=True, null=True)
    
    visible_dans_pos = models.BooleanField(default=True)
    ordre_affichage = models.IntegerField(default=0)
    actif = models.BooleanField(default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'restaurant_menus'
        verbose_name = 'Menu'
        verbose_name_plural = 'Menus'
        ordering = ['ordre_affichage', 'nom']
    
    def __str__(self):
        return f"{self.code} - {self.nom}"
    
    def get_cout_revient_total(self, produits_dict=None):
        """
        Calcule le coût de revient total du menu
        Pour les lignes CHOIX : on prend le MAX du groupe (pire cas)
        """
        from collections import defaultdict
        
        produits_dict = produits_dict or {}
        total = 0.0
        groupes_choix = defaultdict(list)
        
        for ligne in self.lignes.all():
            if ligne.type_ligne == 'CHOIX':
                groupes_choix[ligne.groupe].append(ligne)
            else:
                total += ligne.get_cout(produits_dict)
        
        # Pour chaque groupe de choix, prendre le coût maximum
        for groupe, lignes in groupes_choix.items():
            if lignes:
                max_cout = max(l.get_cout(produits_dict) for l in lignes)
                total += max_cout
        
        return total
    
    def get_temps_preparation_realiste(self):
        """
        Temps de préparation réaliste = le plus long (parallélisation)
        Gère aussi les groupes CHOIX
        """
        from collections import defaultdict
        
        max_temps = 0
        groupes_choix = defaultdict(list)
        
        for ligne in self.lignes.all():
            if ligne.type_ligne == 'CHOIX':
                groupes_choix[ligne.groupe].append(ligne)
            else:
                max_temps = max(max_temps, ligne.recette.temps_preparation_minutes)
        
        # Pour chaque groupe de choix, prendre le temps maximum
        for groupe, lignes in groupes_choix.items():
            if lignes:
                max_ligne = max(l.recette.temps_preparation_minutes for l in lignes)
                max_temps = max(max_temps, max_ligne)
        
        return max_temps
    
    @property
    def cout_revient_total(self):
        """Propriété simplifiée (sans produits_dict)"""
        return self.get_cout_revient_total()

    
    def calculer_temps_preparation(self):
        pass

    @property
    def marge(self):
        if self.prix_vente:
            return float(self.prix_vente) - self.get_cout_revient_total()
        return 0
    
    @property
    def marge_pourcentage(self):
        if self.prix_vente and self.prix_vente > 0:
            return (self.marge / float(self.prix_vente)) * 100
        return 0


class LigneMenuModel(models.Model):
    """Ligne d'un menu (recette associée avec typage)"""
    
    GROUPE_CHOICES = [
        ('ENTREE', 'Entrée'),
        ('PLAT', 'Plat principal'),
        ('ACCOMPAGNEMENT', 'Accompagnement'),
        ('BOISSON', 'Boisson'),
        ('DESSERT', 'Dessert'),
    ]
    
    TYPE_LIGNE_CHOICES = [
        ('FIXE', 'Inclus d\'office'),
        ('CHOIX', 'Au choix du client'),
        ('SUPPLEMENT', 'Supplément payant'),
    ]
    
    id = models.CharField(max_length=50, primary_key=True)
    menu = models.ForeignKey(MenuModel, on_delete=models.CASCADE, related_name='lignes')
    recette = models.ForeignKey(RecetteModel, on_delete=models.CASCADE)
    
    # Nouveaux champs stratégiques
    groupe = models.CharField(max_length=20, choices=GROUPE_CHOICES, default='PLAT')
    type_ligne = models.CharField(max_length=20, choices=TYPE_LIGNE_CHOICES, default='FIXE')
    
    quantite = models.IntegerField(default=1)
    prix_supplement = models.DecimalField(max_digits=10, decimal_places=2, default=0, help_text="Si type SUPPLEMENT")
    
    class Meta:
        db_table = 'restaurant_menus_lignes'
        verbose_name = 'Ligne de menu'
        verbose_name_plural = 'Lignes de menu'
        # Plus d'unicité pour permettre la même recette en FIXE et SUPPLEMENT
    
    def __str__(self):
        return f"[{self.get_type_ligne_display()}] {self.recette.nom} ({self.get_groupe_display()})"
    
    def get_cout(self, produits_dict=None):
        """Coût de la ligne (pour FIXE et SUPPLEMENT)"""
        return float(self.quantite) * self.recette.cout_revient(produits_dict or {})
    
    @property
    def est_fixe(self):
        return self.type_ligne == 'FIXE'
    
    @property
    def est_choix(self):
        return self.type_ligne == 'CHOIX'
    
    @property
    def est_supplement(self):
        return self.type_ligne == 'SUPPLEMENT'
    
    
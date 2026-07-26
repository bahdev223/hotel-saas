# apps/stock/services/inventaire_service.py
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from ..models import Inventaire, LigneInventaire, Produit, StockEntrepot, Entrepot
from .mouvement_service import MouvementStockService


class InventaireService:
    """Service centralisé pour les inventaires physiques.

    Workflow : BROUILLON → EN_COURS → TERMINE → VALIDE
    """

    @staticmethod
    @transaction.atomic
    def creer(entrepot, notes="", realise_par="", code=None):
        """Crée un inventaire pour un entrepôt.

        Si un inventaire validé existe déjà pour cet entrepôt, les
        quantités théoriques sont pré-remplies depuis StockEntrepot.
        Sinon (premier inventaire), quantités à 0.
        """
        if not entrepot:
            raise ValueError("Entrepôt requis")

        if Inventaire.objects.filter(entrepot=entrepot, statut='EN_COURS').exists():
            raise ValidationError("Un inventaire est déjà en cours pour cet entrepôt")

        deja_initialise = Inventaire.objects.filter(
            entrepot=entrepot, statut='VALIDE'
        ).exists()

        import uuid
        inventaire = Inventaire.objects.create(
            code=code or f"INV-{uuid.uuid4().hex[:8].upper()}",
            entrepot=entrepot,
            statut='EN_COURS',
            realise_par=realise_par or "Système",
            notes=notes,
        )

        stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit')

        if not deja_initialise:
            for stock in stocks:
                LigneInventaire.objects.create(
                    inventaire=inventaire,
                    produit=stock.produit,
                    quantite_theorique=0,
                    quantite_reelle=0,
                    prix_unitaire=stock.produit.prix_achat or 0,
                )
        else:
            for stock in stocks:
                LigneInventaire.objects.create(
                    inventaire=inventaire,
                    produit=stock.produit,
                    quantite_theorique=stock.quantite,
                    quantite_reelle=stock.quantite,
                    prix_unitaire=stock.produit.prix_achat or 0,
                )

        return inventaire

    @staticmethod
    @transaction.atomic
    def mettre_a_jour_ligne(ligne, quantite_reelle, prix_unitaire=None):
        """Met à jour la quantité réelle et optionnellement le prix."""
        if quantite_reelle < 0:
            raise ValidationError("La quantité réelle ne peut pas être négative")
        ligne.quantite_reelle = Decimal(str(quantite_reelle))
        if prix_unitaire is not None:
            ligne.prix_unitaire = Decimal(str(prix_unitaire))
        ligne.save()
        return ligne

    @staticmethod
    @transaction.atomic
    def valider(inventaire, user=None):
        """Valide un inventaire : ajuste les stocks via MouvementStockService.

        Retourne la liste des ajustements effectués.
        """
        Inventaire.objects.select_for_update().get(id=inventaire.id)

        if inventaire.statut == 'VALIDE':
            raise ValidationError("Inventaire déjà validé")

        est_premier = not Inventaire.objects.filter(
            entrepot=inventaire.entrepot, statut='VALIDE'
        ).exclude(id=inventaire.id).exists()

        ajustements = []

        for ligne in inventaire.lignes.all().select_related('produit'):
            try:
                stock = StockEntrepot.objects.select_for_update().get(
                    entrepot=inventaire.entrepot, produit=ligne.produit
                )
            except StockEntrepot.DoesNotExist:
                stock = StockEntrepot.objects.create(
                    entrepot=inventaire.entrepot, produit=ligne.produit, quantite=0
                )
                stock = StockEntrepot.objects.select_for_update().get(pk=stock.pk)

            ancienne_quantite = stock.quantite
            nouvelle_quantite = ligne.quantite_reelle
            diff = nouvelle_quantite - ancienne_quantite
            valeur = ligne.prix_unitaire or ligne.produit.prix_achat or Decimal('0')
            username = user.username if user else "Système"

            if diff > 0:
                if est_premier:
                    MouvementStockService.initialiser_stock(
                        produit=ligne.produit, entrepot=inventaire.entrepot,
                        quantite=diff, utilisateur=username,
                        valeur_unitaire=valeur, reference=inventaire.code,
                        raison="Stock initial"
                    )
                else:
                    MouvementStockService.entree_stock(
                        produit=ligne.produit, entrepot=inventaire.entrepot,
                        quantite=diff, utilisateur=username,
                        motif='inventaire', valeur_unitaire=valeur,
                        reference=inventaire.code, raison="Correction inventaire"
                    )
            elif diff < 0:
                MouvementStockService.sortie_stock(
                    produit=ligne.produit, entrepot=inventaire.entrepot,
                    quantite=abs(diff), utilisateur=username,
                    motif='inventaire', valeur_unitaire=valeur,
                    reference=inventaire.code, raison="Correction inventaire"
                )

            if est_premier and ligne.prix_unitaire and ligne.prix_unitaire > 0:
                Produit.objects.filter(id=ligne.produit.id).update(prix_achat=ligne.prix_unitaire)

            ajustements.append({
                'produit': ligne.produit.nom,
                'avant': float(ancienne_quantite),
                'apres': float(nouvelle_quantite),
                'diff': float(diff),
            })

        inventaire.statut = 'VALIDE'
        inventaire.date_fin = timezone.now()
        inventaire.save()

        return ajustements

    @staticmethod
    def supprimer(inventaire):
        """Supprime un inventaire non validé."""
        if inventaire.statut == 'VALIDE':
            raise ValidationError("Impossible de supprimer un inventaire validé")
        inventaire.delete()

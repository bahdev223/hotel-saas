# apps/stock/services/achat_service.py
from decimal import Decimal
from django.db import transaction, models
from django.db.models import Q, F
from django.utils import timezone
from django.core.exceptions import ValidationError
from ..models import BonEntree, LigneBonEntree, Produit, Entrepot
from ..models.bon_entree import StatutBonEntree
from .mouvement_service import MouvementStockService


class AchatService:
    """Service centralisé pour les achats / réceptions fournisseurs.

    Sépare la création de la commande (BROUILLON) de la réception
    (partielle ou totale) et de la clôture.
    """

    @staticmethod
    @transaction.atomic
    def creer_commande(fournisseur, lignes_data, entrepot=None,
                       reference_fournisseur="", notes="", user=None,
                       date_commande=None):
        """Crée un bon de commande fournisseur (statut BROUILLON).

        lignes_data = [{'produit_id', 'quantite_commandee', 'prix_achat'}, ...]
        """
        if not fournisseur:
            raise ValueError("Fournisseur requis")
        if not lignes_data:
            raise ValueError("Au moins une ligne requise")
        if not entrepot:
            entrepot = Entrepot.objects.filter(type_entrepot='CENTRAL', actif=True).first()
            if not entrepot:
                raise ValueError("Aucun entrepôt central trouvé")

        bon = BonEntree.objects.create(
            fournisseur=fournisseur,
            entrepot=entrepot,
            reference_fournisseur=reference_fournisseur,
            notes=notes,
            statut=StatutBonEntree.BROUILLON,
            date_commande=date_commande,
            created_by=user,
        )

        total = Decimal('0')
        for ld in lignes_data:
            produit_id = ld.get('produit_id')
            qte = Decimal(str(ld.get('quantite_commandee', ld.get('quantite', 1))))
            prix = Decimal(str(ld.get('prix_achat', 0)))
            if qte <= 0 or prix <= 0:
                continue
            produit = Produit.objects.get(id=produit_id)
            LigneBonEntree.objects.create(
                bon_entree=bon,
                produit=produit,
                quantite_commandee=qte,
                quantite_recue=0,
                prix_achat=prix,
            )
            total += qte * prix

        bon.total = total
        bon.save(update_fields=['total'])
        return bon

    @staticmethod
    @transaction.atomic
    def enregistrer_reception(bon, lignes_recues, user=None):
        """Enregistre une réception (partielle ou totale) pour un bon.

        lignes_recues = [{'ligne_id', 'quantite_recue', ...}]

        Chaque ligne peut être reçue plusieurs fois tant que
        quantite_recue cumulée <= quantite_commandee.
        Crée les mouvements de stock pour les quantités reçues.
        Met à jour le statut du bon si nécessaire.
        """
        if bon.statut == StatutBonEntree.ANNULE:
            raise ValueError("Bon d'entrée annulé, impossible de réceptionner")
        if bon.statut == StatutBonEntree.VALIDE:
            raise ValueError("Bon d'entrée déjà intégralement réceptionné")

        for lr in lignes_recues:
            ligne_id = lr.get('ligne_id')
            quantite_recue = Decimal(str(lr.get('quantite_recue', 0)))
            if quantite_recue <= 0:
                continue

            ligne = LigneBonEntree.objects.select_related('produit').get(id=ligne_id)
            nouveau_total = ligne.quantite_recue + quantite_recue
            if nouveau_total > ligne.quantite_commandee:
                raise ValidationError(
                    f"Réception {quantite_recue} pour {ligne.produit.nom} "
                    f"dépasse le solde ({ligne.ecart})"
                )

            # Mettre à jour la quantité reçue
            ligne.quantite_recue = nouveau_total
            ligne.save()

            # Créer le mouvement de stock
            MouvementStockService.entree_stock(
                produit=ligne.produit,
                entrepot=bon.entrepot,
                quantite=quantite_recue,
                utilisateur=user.username if user else "Système",
                motif='achat',
                valeur_unitaire=float(ligne.prix_achat),
                reference=bon.numero,
                raison=f"Réception {bon.numero} - {bon.fournisseur.nom}",
            )

            # Mettre à jour le prix d'achat du produit
            Produit.objects.filter(id=ligne.produit_id).update(prix_achat=ligne.prix_achat)

        # Mettre à jour le total et le statut du bon
        bon.calculer_totaux()
        AchatService._mettre_a_jour_statut(bon, user)
        return bon

    @staticmethod
    @transaction.atomic
    def cloturer(bon, user=None):
        """Clôture un bon de commande (force le statut final)."""
        if bon.statut in (StatutBonEntree.VALIDE, StatutBonEntree.ANNULE):
            raise ValueError("Bon déjà clôturé")

        lignes_restantes = bon.lignes.filter(quantite_recue__lt=models.F('quantite_commandee'))
        if lignes_restantes.exists():
            bon.statut = StatutBonEntree.PARTIEL
        else:
            bon.statut = StatutBonEntree.VALIDE

        bon.valide_by = user
        bon.valide_at = timezone.now()
        bon.save()
        return bon

    @staticmethod
    def _mettre_a_jour_statut(bon, user=None):
        lignes_restantes = bon.lignes.filter(
            quantite_recue__lt=F('quantite_commandee')
        )
        if lignes_restantes.exists():
            bon.statut = StatutBonEntree.PARTIEL
        else:
            bon.statut = StatutBonEntree.VALIDE
            bon.valide_by = user
            bon.valide_at = timezone.now()
        bon.save()

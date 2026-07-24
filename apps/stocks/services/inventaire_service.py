from datetime import date
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.stocks.models import Inventaire, LigneInventaire, MouvementStock, Article, Depot
from apps.stocks.constants import StatutInventaire


class InventaireService:

    @staticmethod
    @transaction.atomic
    def creer_inventaire(reference, depot, date_inventaire=None, realise_par="", notes=""):
        if date_inventaire is None:
            date_inventaire = date.today()

        inventaire = Inventaire.objects.create(
            reference=reference,
            depot=depot,
            date_inventaire=date_inventaire,
            realise_par=realise_par,
            notes=notes,
        )
        return inventaire

    @staticmethod
    @transaction.atomic
    def ajouter_ligne(inventaire, article, quantite_reelle, lot=None):
        from stocks.services.mouvement_service import _stock_article_depot
        quantite_theorique = _stock_article_depot(article, inventaire.depot)

        ligne, created = LigneInventaire.objects.update_or_create(
            inventaire=inventaire,
            article=article,
            lot=lot,
            defaults={
                "quantite_theorique": quantite_theorique,
                "quantite_reelle": quantite_reelle,
            },
        )
        return ligne

    @staticmethod
    @transaction.atomic
    def valider_inventaire(inventaire, created_by=""):
        from stocks.services.mouvement_service import MouvementStockService

        if inventaire.statut == StatutInventaire.VALIDE:
            return inventaire

        for ligne in inventaire.lignes.select_related("article", "article__comportement"):
            ecart = ligne.ecart
            if ecart == 0:
                continue

            if ecart > 0:
                MouvementStockService.entree_stock(
                    article=ligne.article,
                    depot=inventaire.depot,
                    quantite=abs(ecart),
                    libelle=f"Ajustement inventaire {inventaire.reference}",
                    reference=f"INV-{inventaire.reference}-{ligne.article.id}",
                    lot=ligne.lot,
                    created_by=created_by,
                )
            else:
                MouvementStockService.sortie_stock(
                    article=ligne.article,
                    depot=inventaire.depot,
                    quantite=abs(ecart),
                    libelle=f"Ajustement inventaire {inventaire.reference}",
                    reference=f"INV-{inventaire.reference}-{ligne.article.id}",
                    lot=ligne.lot,
                    created_by=created_by,
                )

        inventaire.statut = StatutInventaire.VALIDE
        inventaire.save(update_fields=["statut"])
        return inventaire

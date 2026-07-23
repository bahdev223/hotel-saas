from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from apps.stocks.constants import NatureMouvement
from apps.stocks.models import MouvementStock, SourceOperation, Valorisation, JournalStock
from apps.stocks.valorisation import ValuationRegistry


class MouvementStockService:

    @staticmethod
    @transaction.atomic
    def entree_stock(
        article,
        depot,
        quantite,
        prix_unitaire=None,
        lot=None,
        emplacement=None,
        libelle="",
        source_operation=None,
        reference=None,
        reference_externe="",
        source=None,
        created_by="",
    ):
        qte = Decimal(quantite)
        if qte <= 0:
            raise ValueError(
                f"QuantitÃ© d'entrÃ©e doit Ãªtre strictement positive : {qte}"
            )
        if reference is None:
            reference = f"E-{timezone.now().strftime('%Y%m%d%H%M%S%f')}-{article.id}"

        mouvement = MouvementStock(
            reference=reference,
            nature=NatureMouvement.ENTREE,
            article=article,
            depot=depot,
            quantite=qte,
            prix_unitaire=prix_unitaire,
            cout_total=qte * prix_unitaire if prix_unitaire else None,
            date_mouvement=timezone.now(),
            libelle=libelle,
            emplacement=emplacement,
            lot=lot,
            source_operation=source_operation,
            reference_externe=reference_externe,
            created_by=created_by,
            valide=True,
        )
        if source is not None:
            mouvement.source = source
        mouvement.save()
        _journaliser(mouvement, created_by)
        if prix_unitaire:
            _mettre_a_jour_valorisation(article, depot, qte, prix_unitaire, mouvement=mouvement)
        return mouvement

    @staticmethod
    @transaction.atomic
    def sortie_stock(
        article,
        depot,
        quantite,
        prix_unitaire=None,
        lot=None,
        emplacement=None,
        libelle="",
        source_operation=None,
        reference=None,
        reference_externe="",
        source=None,
        created_by="",
    ):
        qte = Decimal(quantite)
        if qte <= 0:
            raise ValueError(
                f"QuantitÃ© de sortie doit Ãªtre strictement positive : {qte}"
            )
        if reference is None:
            reference = f"S-{timezone.now().strftime('%Y%m%d%H%M%S%f')}-{article.id}"

        if _stock_article_depot(article, depot) < qte:
            raise ValueError(
                f"Stock insuffisant pour {article.code} @ {depot.code}: "
                f"demandÃ© {qte}, disponible {_stock_article_depot(article, depot)}"
            )

        mouvement = MouvementStock(
            reference=reference,
            nature=NatureMouvement.SORTIE,
            article=article,
            depot=depot,
            quantite=-qte,
            prix_unitaire=prix_unitaire,
            cout_total=qte * prix_unitaire if prix_unitaire else None,
            date_mouvement=timezone.now(),
            libelle=libelle,
            emplacement=emplacement,
            lot=lot,
            source_operation=source_operation,
            reference_externe=reference_externe,
            created_by=created_by,
            valide=True,
        )
        if source is not None:
            mouvement.source = source
        mouvement.save()
        _journaliser(mouvement, created_by)
        strategy = ValuationRegistry.get_strategy(article.methode_valorisation)
        valorisation, _ = Valorisation.objects.get_or_create(
            article=article, depot=depot,
            defaults={"methode": article.methode_valorisation},
        )
        strategy.enregistrer_sortie(valorisation, qte, mouvement=mouvement)
        return mouvement

    @staticmethod
    @transaction.atomic
    def transferer(
        article,
        depot_source,
        depot_destination,
        quantite,
        lot=None,
        libelle="",
        reference_externe="",
        source=None,
        created_by="",
    ):
        now_str = timezone.now().strftime('%Y%m%d%H%M%S%f')
        qte = abs(Decimal(quantite))
        if qte <= 0:
            raise ValueError(
                f"QuantitÃ© de transfert doit Ãªtre strictement positive : {qte}"
            )
        src_op, _ = SourceOperation.objects.get_or_create(
            code="TRANSFERT",
            defaults={"nom": "Transfert", "famille": "LOGISTIQUE", "systeme": True},
        )

        if _stock_article_depot(article, depot_source) < qte and lot is None:
            raise ValueError(
                f"Stock insuffisant pour transfert de {article.code} @ {depot_source.code}: "
                f"demandÃ© {qte}, disponible {_stock_article_depot(article, depot_source)}"
            )
        if lot and lot.quantite_restante < qte:
            raise ValueError(
                f"QuantitÃ© restante insuffisante dans le lot {lot.numero_lot}: "
                f"demandÃ© {qte}, restant {lot.quantite_restante}"
            )

        sortie = MouvementStockService.sortie_stock(
            article=article,
            depot=depot_source,
            quantite=qte,
            lot=lot,
            libelle=libelle or f"Transfert vers {depot_destination.libelle}",
            source_operation=src_op,
            reference_externe=reference_externe,
            reference=f"TRF-S-{now_str}-{article.id}",
            source=source,
            created_by=created_by,
        )

        entree = MouvementStockService.entree_stock(
            article=article,
            depot=depot_destination,
            quantite=qte,
            lot=lot,
            prix_unitaire=sortie.prix_unitaire,
            libelle=libelle or f"Transfert depuis {depot_source.libelle}",
            source_operation=src_op,
            reference_externe=reference_externe,
            reference=f"TRF-E-{now_str}-{article.id}",
            source=source,
            created_by=created_by,
        )

        return sortie, entree


def _stock_article_depot(article, depot):
    from django.db.models import Sum
    total = MouvementStock.objects.filter(
        article=article, depot=depot, valide=True,
    ).aggregate(total=Sum("quantite"))["total"] or Decimal("0")
    return total


def _journaliser(mouvement, created_by=""):
    stock_apres = _stock_article_depot(mouvement.article, mouvement.depot)
    stock_avant = stock_apres - mouvement.quantite

    JournalStock.objects.create(
        mouvement=mouvement,
        article=mouvement.article,
        depot=mouvement.depot,
        date=mouvement.date_mouvement,
        nature=mouvement.nature,
        quantite=mouvement.quantite,
        stock_avant=stock_avant,
        stock_apres=stock_apres,
        cout_unitaire=mouvement.prix_unitaire,
        libelle=mouvement.libelle,
        created_by=created_by or mouvement.created_by,
    )


def _mettre_a_jour_valorisation(article, depot, quantite, prix_unitaire, mouvement=None):
    strategy = ValuationRegistry.get_strategy(article.methode_valorisation)
    valorisation, created = Valorisation.objects.get_or_create(
        article=article,
        depot=depot,
        defaults={
            "methode": article.methode_valorisation,
            "cout_unitaire_moyen": prix_unitaire,
            "quantite_totale": quantite,
            "valeur_totale": quantite * prix_unitaire,
        },
    )
    if created:
        strategy.initialiser(valorisation, quantite, prix_unitaire)
    else:
        strategy.enregistrer_entree(valorisation, quantite, prix_unitaire, mouvement=mouvement)

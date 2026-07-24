from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from apps.stocks.models import Article, TypeArticle, CategorieArticle, Unite, ComportementArticle
from apps.stocks.constants import COMPORTEMENT_PAR_DEFAUT


class ArticleService:

    @staticmethod
    @transaction.atomic
    def creer_article(
        code,
        designation,
        type_article_code,
        unite_code,
        categorie_code=None,
        comportement=None,
        methode_valorisation="PMP",
        seuil_alerte=None,
        stock_min=None,
        stock_max=None,
        description="",
    ):
        type_art = TypeArticle.objects.get(code=type_article_code)
        unite = Unite.objects.get(code=unite_code)

        if comportement is None:
            comportement = ComportementArticle.creer_defaut()

        categorie = None
        if categorie_code:
            categorie = CategorieArticle.objects.get(code=categorie_code)

        article = Article.objects.create(
            code=code,
            designation=designation,
            description=description,
            type_article=type_art,
            categorie=categorie,
            unite_defaut=unite,
            comportement=comportement,
            methode_valorisation=methode_valorisation,
            seuil_alerte=seuil_alerte,
            stock_min=stock_min,
            stock_max=stock_max,
        )
        return article

    @staticmethod
    def get_stock_disponible(article, depot):
        from stocks.models import MouvementStock
        total = MouvementStock.objects.filter(
            article=article, depot=depot, valide=True,
        ).aggregate(total=models.Sum("quantite"))["total"] or Decimal("0")
        return total

    @staticmethod
    def get_stock_global(article):
        from stocks.models import MouvementStock
        total = MouvementStock.objects.filter(
            article=article, valide=True,
        ).aggregate(total=models.Sum("quantite"))["total"] or Decimal("0")
        return total

    @staticmethod
    def articles_en_alerte():
        from django.db.models import Sum, F, OuterRef, Subquery
        from stocks.models import MouvementStock
        sub_total = MouvementStock.objects.filter(
            article=OuterRef("pk"), valide=True,
        ).values("article").annotate(total=Sum("quantite")).values("total")

        articles = Article.objects.filter(
            actif=True, seuil_alerte__isnull=False,
        ).annotate(
            stock_actuel=Subquery(sub_total),
        ).filter(stock_actuel__lte=F("seuil_alerte"))

        return articles

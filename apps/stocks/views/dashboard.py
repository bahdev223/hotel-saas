from datetime import date, timedelta
from django.db.models import Sum, Count
from django.views.generic import TemplateView
from apps.stocks.models import Article, Depot, MouvementStock, Lot, Valorisation
from apps.stocks.services import ArticleService
from apps.stocks.views.base import StockViewMixin


class DashboardView(StockViewMixin, TemplateView):
    template_name = "stocks/dashboard.html"
    section = "dashboard"
    title = "Tableau de bord"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        today = date.today()
        next_month = today + timedelta(days=30)

        context["total_articles"] = Article.objects.filter(actif=True).count()
        context["total_depots"] = Depot.objects.filter(est_actif=True).count()
        context["total_mouvements"] = MouvementStock.objects.count()

        total_val = Valorisation.objects.aggregate(
            total=Sum("valeur_totale"),
            total_qty=Sum("quantite_totale"),
        )
        context["valeur_stock"] = total_val["total"] or 0
        context["quantite_stock"] = total_val["total_qty"] or 0

        context["articles_alerte"] = ArticleService.articles_en_alerte().select_related(
            "type_article", "unite_defaut"
        )[:10]

        context["lots_expirants"] = Lot.objects.filter(
            date_peremption__gte=today,
            date_peremption__lte=next_month,
            actif=True,
        ).select_related("article").order_by("date_peremption")[:10]

        context["derniers_mouvements"] = MouvementStock.objects.select_related(
            "article", "depot", "source_operation"
        ).order_by("-date_mouvement")[:10]

        context["depots"] = Depot.objects.filter(est_actif=True).annotate(
            valeur_stock=Sum("valorisations__valeur_totale"),
            nb_articles=Count("valorisations", distinct=True),
        )

        context["top_articles"] = Valorisation.objects.values(
            "article__code", "article__designation", "article__unite_defaut__code",
        ).annotate(
            valeur_totale=Sum("valeur_totale"),
            quantite_totale=Sum("quantite_totale"),
        ).order_by("-valeur_totale")[:10]

        return context

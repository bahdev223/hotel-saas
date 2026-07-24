from django.views.generic import ListView
from apps.stocks.models import JournalStock
from apps.stocks.views.base import StockViewMixin
from apps.stocks.app_settings import get_config


class JournalStockView(StockViewMixin, ListView):
    model = JournalStock
    template_name = "stocks/journal_stock.html"
    section = "journal"
    title = "Journal de stock"
    paginate_by = 25

    def get_queryset(self):
        qs = JournalStock.objects.select_related("article", "depot", "mouvement")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                article__code__icontains=q
            ) | qs.filter(libelle__icontains=q)
        nature = self.request.GET.get("nature")
        if nature:
            qs = qs.filter(nature=nature)
        depot = self.request.GET.get("depot")
        if depot:
            qs = qs.filter(depot_id=depot)
        article = self.request.GET.get("article")
        if article:
            qs = qs.filter(article_id=article)
        date_debut = self.request.GET.get("date_debut")
        if date_debut:
            qs = qs.filter(date__gte=date_debut)
        date_fin = self.request.GET.get("date_fin")
        if date_fin:
            qs = qs.filter(date__lte=date_fin)
        return qs

    def get_paginate_by(self, queryset):
        config = get_config()
        return self.request.GET.get("pp", config.get("ITEMS_PER_PAGE", 25))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from stocks.constants import NatureMouvement
        from stocks.models import Depot as D
        context["depots"] = D.objects.filter(est_actif=True)
        context["natures"] = NatureMouvement.choices
        return context

from django.db.models import Sum
from django.views.generic import ListView
from apps.stocks.models import Valorisation
from apps.stocks.views.base import StockViewMixin
from apps.stocks.app_settings import get_config


class ValorisationListView(StockViewMixin, ListView):
    model = Valorisation
    template_name = "stocks/valorisation.html"
    section = "valorisation"
    title = "Valorisation des stocks"
    paginate_by = 25

    def get_queryset(self):
        qs = Valorisation.objects.select_related("article", "depot")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(article__code__icontains=q) | qs.filter(
                article__designation__icontains=q
            )
        depot = self.request.GET.get("depot")
        if depot:
            qs = qs.filter(depot_id=depot)
        methode = self.request.GET.get("methode")
        if methode:
            qs = qs.filter(methode=methode)
        return qs

    def get_paginate_by(self, queryset):
        config = get_config()
        return self.request.GET.get("pp", config.get("ITEMS_PER_PAGE", 25))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from stocks.models import Depot as D, Article as A
        context["depots"] = D.objects.filter(est_actif=True)
        totals = Valorisation.objects.aggregate(
            total_quantite=Sum("quantite_totale"),
            total_valeur=Sum("valeur_totale"),
        )
        context["total_quantite"] = totals["total_quantite"] or 0
        context["total_valeur"] = totals["total_valeur"] or 0
        return context

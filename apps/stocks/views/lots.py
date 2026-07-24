from datetime import date
from urllib.parse import urlencode
from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView
from apps.stocks.models import Lot
from apps.stocks.forms import LotForm
from apps.stocks.views.base import StockViewMixin
from apps.stocks.app_settings import get_config


class LotListView(StockViewMixin, ListView):
    model = Lot
    template_name = "stocks/lot_list.html"
    section = "lots"
    title = "Lots"
    paginate_by = 25

    def get_queryset(self):
        qs = Lot.objects.select_related("article")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(numero_lot__icontains=q) | qs.filter(
                article__code__icontains=q
            ) | qs.filter(article__designation__icontains=q)
        peremption = self.request.GET.get("peremption")
        if peremption == "30j":
            from datetime import timedelta
            today = date.today()
            qs = qs.filter(
                date_peremption__gte=today,
                date_peremption__lte=today + timedelta(days=30),
            )
        article = self.request.GET.get("article")
        if article:
            qs = qs.filter(article_id=article)
        actif = self.request.GET.get("actif")
        if actif == "oui":
            qs = qs.filter(actif=True)
        elif actif == "non":
            qs = qs.filter(actif=False)
        return qs

    def get_paginate_by(self, queryset):
        config = get_config()
        return self.request.GET.get("pp", config.get("ITEMS_PER_PAGE", 25))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        from datetime import date
        context["today"] = date.today()
        from stocks.models import Article as A
        context["articles"] = A.objects.filter(actif=True)
        return context


class LotCreateView(StockViewMixin, CreateView):
    model = Lot
    form_class = LotForm
    template_name = "stocks/lot_form.html"
    section = "lots"
    title = "Nouveau lot"
    success_url = reverse_lazy("stocks:lot_list")

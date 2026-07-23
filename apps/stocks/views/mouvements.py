from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView
from apps.stocks.models import MouvementStock
from apps.stocks.forms import MouvementForm
from apps.stocks.views.base import StockViewMixin
from apps.stocks.app_settings import get_config


class MouvementListView(StockViewMixin, ListView):
    model = MouvementStock
    template_name = "stocks/mouvement_list.html"
    section = "mouvements"
    title = "Mouvements de stock"
    paginate_by = 25

    def get_queryset(self):
        qs = MouvementStock.objects.select_related(
            "article", "depot", "source_operation"
        )
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(
                reference__icontains=q
            ) | qs.filter(article__code__icontains=q) | qs.filter(libelle__icontains=q)
        nature = self.request.GET.get("nature")
        if nature:
            qs = qs.filter(nature=nature)
        depot = self.request.GET.get("depot")
        if depot:
            qs = qs.filter(depot_id=depot)
        article = self.request.GET.get("article")
        if article:
            qs = qs.filter(article_id=article)
        source = self.request.GET.get("source")
        if source:
            qs = qs.filter(source_operation_id=source)
        valide = self.request.GET.get("valide")
        if valide == "oui":
            qs = qs.filter(valide=True)
        elif valide == "non":
            qs = qs.filter(valide=False)
        return qs

    def get_paginate_by(self, queryset):
        config = get_config()
        return self.request.GET.get("pp", config.get("ITEMS_PER_PAGE", 25))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        from stocks.constants import NatureMouvement
        from stocks.models import Depot as D, SourceOperation as S
        context["natures"] = NatureMouvement.choices
        context["depots"] = D.objects.filter(est_actif=True)
        context["sources"] = S.objects.filter(active=True)
        return context


class MouvementCreateView(StockViewMixin, CreateView):
    model = MouvementStock
    form_class = MouvementForm
    template_name = "stocks/mouvement_form.html"
    section = "mouvements"
    title = "Nouveau mouvement"
    success_url = reverse_lazy("stocks:mouvement_list")

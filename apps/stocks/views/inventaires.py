from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from apps.stocks.models import Inventaire
from apps.stocks.forms import InventaireForm
from apps.stocks.views.base import StockViewMixin
from apps.stocks.app_settings import get_config


class InventaireListView(StockViewMixin, ListView):
    model = Inventaire
    template_name = "stocks/inventaire_list.html"
    section = "inventaires"
    title = "Inventaires"
    paginate_by = 25

    def get_queryset(self):
        qs = Inventaire.objects.select_related("depot")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(reference__icontains=q)
        statut = self.request.GET.get("statut")
        if statut:
            qs = qs.filter(statut=statut)
        depot = self.request.GET.get("depot")
        if depot:
            qs = qs.filter(depot_id=depot)
        return qs

    def get_paginate_by(self, queryset):
        config = get_config()
        return self.request.GET.get("pp", config.get("ITEMS_PER_PAGE", 25))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        from stocks.models import Depot as D
        context["depots"] = D.objects.filter(est_actif=True)
        return context


class InventaireDetailView(StockViewMixin, DetailView):
    model = Inventaire
    template_name = "stocks/inventaire_form.html"
    section = "inventaires"
    title = "DÃ©tail inventaire"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["lignes"] = self.object.lignes.select_related("article", "lot")
        return context


class InventaireCreateView(StockViewMixin, CreateView):
    model = Inventaire
    form_class = InventaireForm
    template_name = "stocks/inventaire_form.html"
    section = "inventaires"
    title = "Nouvel inventaire"
    success_url = reverse_lazy("stocks:inventaire_list")

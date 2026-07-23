from django.urls import reverse_lazy
from django.views.generic import ListView, CreateView, UpdateView
from apps.stocks.models import Depot
from apps.stocks.forms import DepotForm
from apps.stocks.views.base import StockViewMixin


class DepotListView(StockViewMixin, ListView):
    model = Depot
    template_name = "stocks/depot_list.html"
    section = "depots"
    title = "DÃ©pÃ´ts"
    paginate_by = 25

    def get_queryset(self):
        qs = Depot.objects.all()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(code__icontains=q) | qs.filter(libelle__icontains=q)
        actif = self.request.GET.get("actif")
        if actif == "oui":
            qs = qs.filter(est_actif=True)
        elif actif == "non":
            qs = qs.filter(est_actif=False)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["q"] = self.request.GET.get("q", "")
        return context


class DepotCreateView(StockViewMixin, CreateView):
    model = Depot
    form_class = DepotForm
    template_name = "stocks/depot_form.html"
    section = "depots"
    title = "Nouveau dÃ©pÃ´t"
    success_url = reverse_lazy("stocks:depot_list")


class DepotUpdateView(StockViewMixin, UpdateView):
    model = Depot
    form_class = DepotForm
    template_name = "stocks/depot_form.html"
    section = "depots"
    title = "Modifier le dÃ©pÃ´t"
    success_url = reverse_lazy("stocks:depot_list")

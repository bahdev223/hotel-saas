from django.urls import reverse_lazy
from django.views.generic import ListView, DetailView, CreateView, UpdateView
from apps.stocks.models import Article, MouvementStock, Lot, Valorisation, JournalStock
from apps.stocks.forms import ArticleForm
from apps.stocks.views.base import StockViewMixin
from apps.stocks.app_settings import get_config


class ArticleListView(StockViewMixin, ListView):
    model = Article
    template_name = "stocks/article_list.html"
    section = "articles"
    title = "Articles"
    paginate_by = 25

    def get_queryset(self):
        qs = Article.objects.select_related("type_article", "unite_defaut", "comportement")
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(code__icontains=q) | qs.filter(designation__icontains=q)
        t = self.request.GET.get("type")
        if t:
            qs = qs.filter(type_article__code=t)
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
        from stocks.models import TypeArticle
        context["types_article"] = TypeArticle.objects.all()
        return context


class ArticleDetailView(StockViewMixin, DetailView):
    model = Article
    template_name = "stocks/article_detail.html"
    section = "articles"
    title = "Fiche article"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        article = self.object

        context["stock_par_depot"] = Valorisation.objects.filter(
            article=article
        ).select_related("depot")

        context["mouvements"] = MouvementStock.objects.filter(
            article=article
        ).select_related("depot", "source_operation").order_by("-date_mouvement")[:20]

        context["lots"] = Lot.objects.filter(article=article, actif=True)

        context["journal"] = JournalStock.objects.filter(
            article=article
        ).select_related("depot").order_by("-date")[:20]

        return context


class ArticleCreateView(StockViewMixin, CreateView):
    model = Article
    form_class = ArticleForm
    template_name = "stocks/article_form.html"
    section = "articles"
    title = "Nouvel article"
    success_url = reverse_lazy("stocks:article_list")


class ArticleUpdateView(StockViewMixin, UpdateView):
    model = Article
    form_class = ArticleForm
    template_name = "stocks/article_form.html"
    section = "articles"
    title = "Modifier l'article"
    success_url = reverse_lazy("stocks:article_list")

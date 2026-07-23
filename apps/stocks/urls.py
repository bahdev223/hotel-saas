from django.urls import path
from apps.stocks.views.dashboard import DashboardView
from apps.stocks.views.articles import ArticleListView, ArticleDetailView, ArticleCreateView, ArticleUpdateView
from apps.stocks.views.depots import DepotListView, DepotCreateView, DepotUpdateView
from apps.stocks.views.mouvements import MouvementListView, MouvementCreateView
from apps.stocks.views.inventaires import InventaireListView, InventaireDetailView, InventaireCreateView
from apps.stocks.views.lots import LotListView, LotCreateView
from apps.stocks.views.journal import JournalStockView
from apps.stocks.views.valorisation import ValorisationListView

app_name = "stocks"

urlpatterns = [
    path("", DashboardView.as_view(), name="dashboard"),
    path("articles/", ArticleListView.as_view(), name="article_list"),
    path("articles/creer/", ArticleCreateView.as_view(), name="article_create"),
    path("articles/<int:pk>/", ArticleDetailView.as_view(), name="article_detail"),
    path("articles/<int:pk>/modifier/", ArticleUpdateView.as_view(), name="article_update"),
    path("depots/", DepotListView.as_view(), name="depot_list"),
    path("depots/creer/", DepotCreateView.as_view(), name="depot_create"),
    path("depots/<int:pk>/modifier/", DepotUpdateView.as_view(), name="depot_update"),
    path("mouvements/", MouvementListView.as_view(), name="mouvement_list"),
    path("mouvements/creer/", MouvementCreateView.as_view(), name="mouvement_create"),
    path("inventaires/", InventaireListView.as_view(), name="inventaire_list"),
    path("inventaires/creer/", InventaireCreateView.as_view(), name="inventaire_create"),
    path("inventaires/<int:pk>/", InventaireDetailView.as_view(), name="inventaire_detail"),
    path("lots/", LotListView.as_view(), name="lot_list"),
    path("lots/creer/", LotCreateView.as_view(), name="lot_create"),
    path("journal/", JournalStockView.as_view(), name="journal_stock"),
    path("valorisation/", ValorisationListView.as_view(), name="valorisation"),
]

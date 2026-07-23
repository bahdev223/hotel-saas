from django.urls import path
from .views import home, index, patron, widgets, brasserie_dashboard, brasserie_produits, brasserie_ajouter_api, brasserie_modifier_api, brasserie_modifier_stock_api, brasserie_supprimer

app_name = 'dashboard'

urlpatterns = [
    path('', home, name='home'),
    path('index/', index, name='index'),
    path('patron/', patron.patron_dashboard, name='patron_dashboard'),
    path('widget/<str:widget_code>/', widgets.widget_data, name='widget_data'),
    path('brasserie/', brasserie_dashboard, name='brasserie'),
    path('brasserie/produits/', brasserie_produits, name='brasserie_produits'),
    path('brasserie/produits/ajouter/', brasserie_ajouter_api, name='brasserie_ajouter_api'),
    path('brasserie/produits/<str:produit_id>/modifier/', brasserie_modifier_api, name='brasserie_modifier_api'),
    path('brasserie/produits/<str:produit_id>/modifier-stock/', brasserie_modifier_stock_api, name='brasserie_modifier_stock_api'),
    path('brasserie/produits/<str:produit_id>/supprimer/', brasserie_supprimer, name='brasserie_supprimer'),
]


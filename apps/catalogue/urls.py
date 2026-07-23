from django.urls import path
from .views import catalogue, api

app_name = 'catalogue'

urlpatterns = [
    path('', catalogue.index, name='index'),
    path('api/items/', api.items, name='api_items'),
]

from django.urls import path

from . import views

app_name = "entreprises"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("editer/", views.editer_entreprise, name="editer"),
    path("etablissement/editer/", views.editer_etablissement, name="editer_etablissement"),
    path("configuration/", views.configuration, name="configuration"),
    path("configuration-hoteliere/", views.configuration_hoteliere, name="configuration_hoteliere"),
    path("modules/", views.modules, name="modules"),
    path("sequences/", views.sequences, name="sequences"),
]

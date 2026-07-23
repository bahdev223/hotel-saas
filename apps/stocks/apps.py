from django.apps import AppConfig


class StocksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.stocks"
    verbose_name = "Stocks — Moteur universel de gestion d'articles et mouvements de stock"

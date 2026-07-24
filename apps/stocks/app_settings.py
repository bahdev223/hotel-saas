from django.conf import settings

DEFAULTS = {
    "BASE_TEMPLATE": "stocks/base.html",
    "THEME": None,
    "ITEMS_PER_PAGE": 25,
}


def get_config():
    config = DEFAULTS.copy()
    config.update(getattr(settings, "STOCKS", {}))
    return config

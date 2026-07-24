from django.views.generic.base import ContextMixin
from apps.stocks.app_settings import get_config


class StockViewMixin(ContextMixin):
    section = ""
    title = ""

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        config = get_config()
        context["base_template"] = config.get("BASE_TEMPLATE", "stocks/base.html")
        context["stocks_config"] = config
        context["section"] = self.section
        context["title"] = self.title
        return context

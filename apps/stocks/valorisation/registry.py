from importlib import import_module

from django.conf import settings


class ValuationRegistry:
    _strategies = {}
    _loaded = False

    STRATEGIES_PAR_DEFAUT = {
        "PMP": "stocks.valorisation.pmp.PMPStrategy",
        "FIFO": "stocks.valorisation.fifo.FIFOStrategy",
        "STANDARD": "stocks.valorisation.standard.StandardCostStrategy",
    }

    @classmethod
    def _charger(cls):
        if cls._loaded:
            return
        config = getattr(settings, "STOCKS_VALUATION_STRATEGIES", {})
        toutes = {**cls.STRATEGIES_PAR_DEFAUT, **config}
        for code, chemin in toutes.items():
            try:
                module_path, class_name = chemin.rsplit(".", 1)
                module = import_module(module_path)
                strategy_class = getattr(module, class_name)
                if strategy_class.method_code:
                    cls._strategies[strategy_class.method_code] = strategy_class
            except Exception:
                pass
        cls._loaded = True

    @classmethod
    def register(cls, strategy_class):
        if strategy_class.method_code:
            cls._strategies[strategy_class.method_code] = strategy_class

    @classmethod
    def get_strategy(cls, method_code):
        cls._charger()
        strategy = cls._strategies.get(method_code)
        if strategy is None:
            cls._charger()
            from stocks.valorisation.pmp import PMPStrategy
            strategy = PMPStrategy
        return strategy

    @classmethod
    def get_choices(cls):
        cls._charger()
        return [
            (code, strategy.method_name)
            for code, strategy in cls._strategies.items()
        ]

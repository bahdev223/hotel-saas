from apps.stocks.valorisation.registry import ValuationRegistry
from apps.stocks.valorisation.base import BaseValuationStrategy
from apps.stocks.valorisation.pmp import PMPStrategy
from apps.stocks.valorisation.fifo import FIFOStrategy
from apps.stocks.valorisation.standard import StandardCostStrategy

ValuationRegistry.register(PMPStrategy)
ValuationRegistry.register(FIFOStrategy)
ValuationRegistry.register(StandardCostStrategy)

__all__ = [
    "ValuationRegistry",
    "BaseValuationStrategy",
    "PMPStrategy",
    "FIFOStrategy",
    "StandardCostStrategy",
]

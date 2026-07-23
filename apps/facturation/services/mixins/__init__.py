# apps/facturation/services/mixins/__init__.py
from .tva_mixin import TVAMixin
from .total_mixin import TotalMixin
from .paiement_mixin import PaiementMixin

__all__ = [
    'TVAMixin',
    'TotalMixin',
    'PaiementMixin',
]


from apps.clients.models import Client
from .unite import UniteModel
from .location import LocationModel

ClientModel = Client  # backward compatibility alias

__all__ = ['ClientModel', 'Client', 'UniteModel', 'LocationModel']
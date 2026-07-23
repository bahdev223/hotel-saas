# Stub for migration compatibility
from apps.clients.models import generate_client_id, Client
ClientModel = Client
__all__ = ['generate_client_id', 'ClientModel']

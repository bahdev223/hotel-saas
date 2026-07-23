from typing import List, Optional
from django.db import models as db_models
from django.core.exceptions import ObjectDoesNotExist

from .models import Client


class ClientRepository:

    def get_all(self, actif: bool = True) -> List[Client]:
        qs = Client.objects.all()
        if actif:
            qs = qs.filter(statut='ACTIF')
        return list(qs)

    def get(self, client_id: str) -> Optional[Client]:
        try:
            return Client.objects.get(id=client_id)
        except ObjectDoesNotExist:
            return None

    def search(self, terme: str) -> List[Client]:
        return list(Client.objects.filter(
            db_models.Q(nom__icontains=terme) |
            db_models.Q(prenom__icontains=terme) |
            db_models.Q(telephone__icontains=terme) |
            db_models.Q(id__icontains=terme)
        ))

    def delete(self, client_id: str) -> bool:
        try:
            Client.objects.get(id=client_id).delete()
            return True
        except ObjectDoesNotExist:
            return False

    def update_statut(self, client_id: str, nouveau_statut: str) -> Optional[Client]:
        try:
            client = Client.objects.get(id=client_id)
            client.statut = nouveau_statut
            client.save()
            return client
        except ObjectDoesNotExist:
            return None

    def count_by_type(self) -> dict:
        counts = {}
        for type_value, _ in Client.TYPE_CLIENT_CHOICES:
            counts[type_value] = Client.objects.filter(type_client=type_value).count()
        return counts

    def count_by_statut(self) -> dict:
        counts = {}
        for statut_value, _ in Client.STATUT_CHOICES:
            counts[statut_value] = Client.objects.filter(statut=statut_value).count()
        return counts

    def get_model(self):
        return Client

# apps/stock/models/fournisseur.py
# Modèle déplacé vers apps.fournisseurs
import uuid
from apps.fournisseurs.models import Fournisseur


def generate_id():
    return str(uuid.uuid4())[:8]

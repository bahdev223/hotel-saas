# apps/authentication/auth_backend.py
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import User
from apps.rh.models import Employe


class MatriculeAuthBackend(ModelBackend):
    """Authentifie un employé par son matricule + mot de passe"""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None or password is None:
            return None
        try:
            employe = Employe.objects.get(matricule=username.upper())
        except Employe.DoesNotExist:
            return None
        if not employe.user or not employe.user.is_active:
            return None
        if employe.user.check_password(password):
            return employe.user
        return None

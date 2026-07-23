from typing import Optional
from django.contrib.auth.models import User
from .models import Employe as EmployeModel


class RhRepository:
    """Repository RH : gestion des employés et comptes utilisateurs"""

    @staticmethod
    def lier_employe_a_user(matricule: str, user: User) -> EmployeModel:
        """Lie un employé à un User Django"""
        employe = EmployeModel.objects.get(matricule=matricule)
        employe.user = user
        employe.save()
        return employe

    @staticmethod
    def get_user_by_matricule(matricule: str) -> Optional[User]:
        """Récupère le User lié à un matricule"""
        try:
            employe = EmployeModel.objects.get(matricule=matricule)
            return employe.user
        except EmployeModel.DoesNotExist:
            return None

    @staticmethod
    def get_employe_by_user(user: User) -> Optional[EmployeModel]:
        """Récupère l'employé à partir d'un User"""
        try:
            return EmployeModel.objects.get(user=user)
        except EmployeModel.DoesNotExist:
            return None

    @staticmethod
    def creer_compte_utilisateur(username: str, password: str, email: str = '') -> User:
        """Crée un compte User Django"""
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email
        )
        return user

    @staticmethod
    def creer_employe_avec_compte(employe_data: dict, user_data: dict) -> tuple[EmployeModel, User]:
        """Crée un employé et son compte User"""
        employe = EmployeModel.objects.create(**employe_data)
        password = user_data.get('password') or user_data['username']
        user = User.objects.create_user(
            username=user_data['username'],
            password=password,
            email=user_data.get('email', '')
        )
        employe.user = user
        employe.save()
        return employe, user

# apps/rh/permissions.py
from apps.authentication.groups import PATRON, MANAGER, RH


def user_can_gerer_rh(user):
    """Seuls PATRON/MANAGER/RH ou superuser peuvent gérer les données RH
    (employés, comptes utilisateurs, départements, postes)."""
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[PATRON, MANAGER, RH]).exists()

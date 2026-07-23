# apps/authentication/decorators.py
from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps


def role_required(allowed_groups):
    """
    Décorateur pour vérifier que l'utilisateur appartient à un groupe autorisé
    
    Utilisation:
        @role_required(['RECEPTION', 'DIRECTION'])
        def ma_vue(request):
            ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('authentication:login')
            
            # Superuser a accès à tout
            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            
            # Vérifier si l'utilisateur a un des groupes autorisés
            if request.user.groups.filter(name__in=allowed_groups).exists():
                return view_func(request, *args, **kwargs)
            
            messages.error(request, 'Vous n\'avez pas accès à cette page')
            return redirect('dashboard:index')
        return wrapper
    return decorator


def groupe_requis(groupe_nom):
    """Décorateur simplifié pour un seul groupe"""
    return role_required([groupe_nom])


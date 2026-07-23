from django.urls import reverse
from django.shortcuts import redirect
from .groups import PATRON, MANAGER, RECEPTION, CUISINE, STOCK, COMPTABLE, RH, TECHNIQUE, SECURITE, RAF


def redirect_by_group(user):
    """
    Redirige l'utilisateur vers son interface selon son groupe.
    Si l'employé a un planning, il va sur employe_accueil quel que soit son groupe.
    """
    if not user.is_authenticated:
        return 'authentication:login'

    if user.is_superuser:
        return 'dashboard:index'

    groups = list(user.groups.values_list('name', flat=True))
    if not groups:
        return 'authentication:employe_accueil'

    # Si l'employé a un planning → POS direct si 1 seul PV, sinon page accueil
    try:
        employe = user.employe
    except:
        employe = None
    if employe:
        from apps.pos.models import SessionPlanning, PointVente
        planning_qs = SessionPlanning.objects.filter(employe=employe).exclude(statut='ANNULE')
        if planning_qs.exists():
            return 'authentication:employe_accueil'

    ROUTES = {
        PATRON: 'dashboard:patron_dashboard',
        MANAGER: 'dashboard:index',
        RECEPTION: 'hotel:dashboard',
        CUISINE: 'pos:cuisine_dashboard',
        STOCK: 'stock:dashboard',
        COMPTABLE: 'comptabilite:dashboard',
        RAF: 'authentication:mon_profil',
        RH: 'rh:dashboard',
        TECHNIQUE: 'dashboard:index',
        SECURITE: 'dashboard:index',
    }

    premier_groupe = groups[0]
    if premier_groupe in ROUTES:
        return ROUTES[premier_groupe]

    # CAISSIER, BAR, RESTAURANT, et tout autre groupe → page accueil employé
    return 'authentication:employe_accueil'


def get_dashboard_url_by_group(user):
    """Retourne l'URL complète du dashboard selon le groupe"""
    route = redirect_by_group(user)
    if isinstance(route, tuple):
        return reverse(route[0], kwargs=route[1])
    return reverse(route)


def redirect_to_group_home(user):
    """Retourne un HttpResponseRedirect selon le groupe de l'utilisateur"""
    route = redirect_by_group(user)
    if isinstance(route, tuple):
        return redirect(route[0], **route[1])
    return redirect(route)


def get_client_ip(request):
    """Récupère l'IP du client"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')

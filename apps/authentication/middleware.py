from django.shortcuts import redirect
from django.urls import resolve
from django.contrib import messages
from django.db.models import Q
from .groups import PATRON, MANAGER, COMPTABLE, PROMOTEUR, RAF
from .permissions import est_lecture_seule

GROUPES_ACCES_TOTAL = [PATRON, MANAGER, COMPTABLE, PROMOTEUR, RAF]

URLS_AUTORISEES_EMPLOYE = [
    '/auth/accueil/',
    '/auth/profil/',
    '/auth/changer-mdp/',
    '/auth/logout/',
    '/paiements/api/',
]


class EmployeeAccessMiddleware:
    """Restreint l'accès des employés aux seules pages autorisées"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            return self.get_response(request)

        if request.user.is_superuser:
            return self.get_response(request)

        groups = list(request.user.groups.values_list('name', flat=True))
        if any(g in GROUPES_ACCES_TOTAL for g in groups):
            return self.get_response(request)

        path = request.path

        # Pages autorisées pour tous les employés
        for url in URLS_AUTORISEES_EMPLOYE:
            if path.startswith(url):
                return self.get_response(request)

        # POS : accès si employé a un planning (sauf ANNULE) ou un point_vente direct
        if path.startswith('/pos/'):
            try:
                employe = request.user.employe
            except:
                employe = None
            if employe and (path == '/pos/mon-espace/' or employe.point_vente):
                return self.get_response(request)
            if employe:
                from apps.pos.models import SessionPlanning
                if SessionPlanning.objects.filter(
                    employe=employe
                ).exclude(statut='ANNULE').exists():
                    return self.get_response(request)

        # Redirection vers accueil employé
        messages.warning(request, "Accès non autorisé")
        return redirect('authentication:employe_accueil')


PROMOTEUR_BLOCKED_PREFIXES = ["/stock/", "/comptabilite/", "/tresorerie/", "/restaurant/"]


class LectureSeuleMiddleware:
    """Bloque les requêtes POST/PUT/PATCH/DELETE de PROMOTEUR sur les zones sensibles"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if est_lecture_seule(request.user) and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if any(request.path.startswith(p) for p in PROMOTEUR_BLOCKED_PREFIXES):
                messages.error(request, "Action non autorisée (lecture seule).")
                return redirect(request.META.get('HTTP_REFERER', '/dashboard/'))
        return self.get_response(request)

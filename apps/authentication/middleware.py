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

        for url in URLS_AUTORISEES_EMPLOYE:
            if path.startswith(url):
                return self.get_response(request)

        if path.startswith('/pos/'):
            try:
                employe = request.user.employe
            except:
                employe = None
            if employe:
                from apps.pos.models import AffectationPointVente
                if AffectationPointVente.objects.filter(employe=employe, actif=True).exists():
                    return self.get_response(request)
                from apps.pos.models import ShiftEmploye
                if ShiftEmploye.objects.filter(
                    affectation__employe=employe
                ).exclude(statut='ANNULE').exists():
                    return self.get_response(request)

        messages.warning(request, "Acc\u00e8s non autoris\u00e9")
        return redirect('authentication:employe_accueil')


PROMOTEUR_BLOCKED_PREFIXES = ["/stock/", "/comptabilite/", "/tresorerie/", "/restaurant/"]


class LectureSeuleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if est_lecture_seule(request.user) and request.method in ("POST", "PUT", "PATCH", "DELETE"):
            if any(request.path.startswith(p) for p in PROMOTEUR_BLOCKED_PREFIXES):
                messages.error(request, "Action non autoris\u00e9e (lecture seule).")
                return redirect(request.META.get('HTTP_REFERER', '/dashboard/'))
        return self.get_response(request)

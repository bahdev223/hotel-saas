# apps/restaurant/views/dashboard.py
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from apps.pos.constants import ActionPOS, TypePointVente
from apps.pos.services.access_service import POSAccessService


@login_required
def dashboard(request):
    """Dashboard de supervision Restaurant."""
    report_points = POSAccessService.points_accessibles(
        user=request.user,
        action=ActionPOS.CONSULTER_RAPPORTS,
    ).filter(type=TypePointVente.RESTAURATION)

    if not report_points.exists():
        salle_points = POSAccessService.points_accessibles(
            user=request.user,
            action=ActionPOS.GERER_SALLE,
        ).filter(type=TypePointVente.RESTAURATION)
        if salle_points.exists():
            return redirect("restaurant:salle_dashboard")

        cuisine_points = POSAccessService.points_accessibles(
            user=request.user,
            action=ActionPOS.GERER_CUISINE,
        ).filter(type=TypePointVente.RESTAURATION)
        if cuisine_points.exists():
            return redirect("restaurant:cuisine_dashboard")

        messages.error(request, "Aucun accès Restaurant autorisé pour votre profil.")
        return redirect("dashboard:index")

    return render(
        request,
        "restaurant/dashboard.html",
        {"points_restaurant": report_points},
    )

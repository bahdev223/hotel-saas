from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from apps.pos.constants import ActionPOS, TypePointVente
from apps.pos.services.access_service import POSAccessService
from ..models import FileAttenteModel, TableModel
from ..services.restaurant_service import RestaurantService, RestaurantWorkflowError


def _restaurants_accessibles(user):
    return POSAccessService.points_accessibles(
        user=user,
        action=ActionPOS.GERER_SALLE,
    ).filter(type=TypePointVente.RESTAURATION)


@login_required
def file_attente(request):
    """File d'attente par Restaurant, reliée aux vraies tables de salle."""
    points = _restaurants_accessibles(request.user)
    point_id = request.POST.get("point_vente") or request.GET.get("point_vente")
    point = points.filter(pk=point_id).first() if point_id else points.first()
    if point is None:
        messages.error(request, "Aucun Restaurant accessible pour gérer la file d'attente.")
        return redirect("restaurant:dashboard")

    employe = getattr(request.user, "employe", None)
    if employe is None:
        messages.error(request, "Un profil employé est requis.")
        return redirect("restaurant:dashboard")

    if request.method == "POST":
        action = request.POST.get("action")
        try:
            if action == "ajouter":
                nombre = max(1, int(request.POST.get("nombre_personnes", 1)))
                FileAttenteModel.objects.create(
                    point_vente=point,
                    nombre_personnes=nombre,
                    nom_client=(request.POST.get("nom_client") or "").strip(),
                    telephone=(request.POST.get("telephone") or "").strip(),
                    statut="EN_ATTENTE",
                )
                messages.success(request, "Client ajouté à la file d'attente.")

            elif action == "placer":
                entry = get_object_or_404(
                    FileAttenteModel,
                    id=request.POST.get("file_id"),
                    statut="EN_ATTENTE",
                    point_vente=point,
                )
                table = get_object_or_404(
                    TableModel.objects.select_related("salle__point_vente"),
                    id=request.POST.get("table_id"),
                    actif=True,
                    salle__point_vente=point,
                )
                if table.capacite < entry.nombre_personnes:
                    raise RestaurantWorkflowError(
                        f"Table {table.numero}: {table.capacite} places pour "
                        f"{entry.nombre_personnes} personne(s)."
                    )

                RestaurantService.occuper_table(
                    table=table,
                    employe=employe,
                    user=request.user,
                    nombre_couverts=entry.nombre_personnes,
                )
                entry.table = table
                entry.table_assigned = table.numero
                entry.statut = "PLACE"
                entry.save(update_fields=["table", "table_assigned", "statut"])
                messages.success(
                    request,
                    f"{entry.nom_client or 'Client'} placé à la table {table.numero}.",
                )

            elif action == "parti":
                entry = get_object_or_404(
                    FileAttenteModel,
                    id=request.POST.get("file_id"),
                    statut="EN_ATTENTE",
                    point_vente=point,
                )
                entry.statut = "PARTI"
                entry.save(update_fields=["statut"])
                messages.success(request, "Client retiré de la file d'attente.")

            else:
                messages.error(request, "Action inconnue.")

        except (ValueError, RestaurantWorkflowError) as exc:
            messages.error(request, str(exc))

        return redirect(
            f"{reverse('restaurant:file_attente')}?point_vente={point.id}"
        )

    file_attente = FileAttenteModel.objects.filter(
        point_vente=point,
        statut="EN_ATTENTE",
    ).order_by("date_entree")

    tables_libres = (
        TableModel.objects.filter(
            salle__point_vente=point,
            salle__actif=True,
            actif=True,
            statut="LIBRE",
        )
        .select_related("salle")
        .order_by("salle__ordre", "salle__nom", "numero")
    )

    return render(request, "restaurant/file_attente.html", {
        "points": points,
        "point_vente": point,
        "file_attente": file_attente,
        "tables_libres": tables_libres,
    })

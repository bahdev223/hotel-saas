from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction

from ..models import TypeChambre, TypeTarif, PlanTarifaire, TarifChambre, CreneauTarifaire
from ..services.tarification_service import TarificationService
from apps.entreprises.services import obtenir_etablissement_actuel


@login_required
def grille_tarifs(request):
    etablissement = obtenir_etablissement_actuel()
    if not etablissement:
        messages.error(request, "Aucun établissement configuré.")
        return redirect("entreprises:dashboard")

    tarifs = TarificationService.tarifs_par_type_chambre(etablissement)
    types_chambres = TypeChambre.objects.filter(actif=True).order_by("ordre")
    plans = PlanTarifaire.objects.filter(etablissement=etablissement, actif=True)
    types_tarif = TypeTarif.objects.filter(actif=True)

    context = {
        "tarifs": tarifs,
        "types_chambres": types_chambres,
        "plans": plans,
        "types_tarif": types_tarif,
        "grille": TarificationService.resumer_grille(etablissement),
    }
    return render(request, "hotel/tarifs/grille.html", context)


@login_required
def ajouter_tarif(request):
    etablissement = obtenir_etablissement_actuel()
    if not etablissement:
        messages.error(request, "Aucun établissement configuré.")
        return redirect("entreprises:dashboard")

    if request.method == "POST":
        try:
            TarifChambre.objects.create(
                etablissement=etablissement,
                type_chambre_id=request.POST.get("type_chambre"),
                plan_tarifaire_id=request.POST.get("plan_tarifaire"),
                type_tarif_id=request.POST.get("type_tarif"),
                montant=request.POST.get("montant"),
                nombre_personnes_incluses=request.POST.get("nombre_personnes_incluses", 1),
                supplement_adulte=request.POST.get("supplement_adulte", 0),
                supplement_enfant=request.POST.get("supplement_enfant", 0),
            )
            messages.success(request, "Tarif ajouté.")
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
        return redirect("hotel:grille_tarifs")

    context = {
        "types_chambres": TypeChambre.objects.filter(actif=True),
        "plans": PlanTarifaire.objects.filter(etablissement=etablissement, actif=True),
        "types_tarif": TypeTarif.objects.filter(actif=True),
    }
    return render(request, "hotel/tarifs/ajouter.html", context)


@login_required
def modifier_tarif(request, tarif_id):
    tarif = get_object_or_404(TarifChambre, id=tarif_id)

    if request.method == "POST":
        try:
            tarif.type_chambre_id = request.POST.get("type_chambre")
            tarif.plan_tarifaire_id = request.POST.get("plan_tarifaire")
            tarif.type_tarif_id = request.POST.get("type_tarif")
            tarif.montant = request.POST.get("montant")
            tarif.nombre_personnes_incluses = request.POST.get("nombre_personnes_incluses", 1)
            tarif.supplement_adulte = request.POST.get("supplement_adulte", 0)
            tarif.supplement_enfant = request.POST.get("supplement_enfant", 0)
            tarif.actif = request.POST.get("actif") == "on"
            tarif.save()
            messages.success(request, "Tarif mis à jour.")
        except Exception as e:
            messages.error(request, f"Erreur : {e}")
        return redirect("hotel:grille_tarifs")

    context = {
        "tarif": tarif,
        "types_chambres": TypeChambre.objects.filter(actif=True),
        "plans": PlanTarifaire.objects.filter(etablissement=tarif.etablissement, actif=True),
        "types_tarif": TypeTarif.objects.filter(actif=True),
    }
    return render(request, "hotel/tarifs/modifier.html", context)


@login_required
def desactiver_tarif(request, tarif_id):
    tarif = get_object_or_404(TarifChambre, id=tarif_id)
    tarif.actif = not tarif.actif
    tarif.save(update_fields=["actif"])
    messages.success(request, f"Tarif {'activé' if tarif.actif else 'désactivé'}.")
    return redirect("hotel:grille_tarifs")


@login_required
def liste_plans(request):
    etablissement = obtenir_etablissement_actuel()
    plans = PlanTarifaire.objects.filter(etablissement=etablissement) if etablissement else []
    return render(request, "hotel/tarifs/plans.html", {"plans": plans})


@login_required
def liste_types_tarif(request):
    types = TypeTarif.objects.all()
    return render(request, "hotel/tarifs/types_tarif.html", {"types": types})


@login_required
def liste_creneaux(request):
    creneaux = CreneauTarifaire.objects.select_related("type_tarif").all()
    return render(request, "hotel/tarifs/creneaux.html", {"creneaux": creneaux})

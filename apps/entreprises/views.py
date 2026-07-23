from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages

from .models import (
    Entreprise,
    Etablissement,
    ConfigurationEntreprise,
    ConfigurationHoteliere,
    ModuleEntreprise,
    SequenceDocument,
)
from .forms import (
    EntrepriseForm,
    EtablissementForm,
    ConfigurationEntrepriseForm,
    ConfigurationHoteliereForm,
    ModuleEntrepriseForm,
)
from .services import obtenir_entreprise_actuelle, obtenir_etablissement_actuel
@staff_member_required
def dashboard(request):
    entreprise = obtenir_entreprise_actuelle()
    etablissement = obtenir_etablissement_actuel()
    config = getattr(entreprise, "configuration", None) if entreprise else None
    modules = ModuleEntreprise.objects.filter(entreprise=entreprise) if entreprise else []

    context = {
        "entreprise": entreprise,
        "etablissement": etablissement,
        "config": config,
        "modules": modules,
    }
    return render(request, "entreprises/dashboard.html", context)


@staff_member_required
def editer_entreprise(request):
    entreprise = obtenir_entreprise_actuelle()

    if request.method == "POST":
        form = EntrepriseForm(request.POST, request.FILES, instance=entreprise)
        if form.is_valid():
            form.save()
            messages.success(request, "Entreprise mise à jour.")
            return redirect("entreprises:dashboard")
    else:
        form = EntrepriseForm(instance=entreprise)

    return render(request, "entreprises/form.html", {
        "form": form,
        "titre": "Informations de l'entreprise",
    })


@staff_member_required
def editer_etablissement(request):
    etablissement = obtenir_etablissement_actuel()
    entreprise = obtenir_entreprise_actuelle()

    if request.method == "POST":
        form = EtablissementForm(request.POST, instance=etablissement)
        if form.is_valid():
            form.save()
            messages.success(request, "Établissement mis à jour.")
            return redirect("entreprises:dashboard")
    else:
        form = EtablissementForm(instance=etablissement)

    return render(request, "entreprises/form.html", {
        "form": form,
        "titre": "Informations de l'établissement",
    })


@staff_member_required
def configuration(request):
    entreprise = obtenir_entreprise_actuelle()
    config = getattr(entreprise, "configuration", None) if entreprise else None

    if request.method == "POST":
        form = ConfigurationEntrepriseForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuration mise à jour.")
            return redirect("entreprises:configuration")
    else:
        form = ConfigurationEntrepriseForm(instance=config)

    return render(request, "entreprises/form.html", {
        "form": form,
        "titre": "Configuration générale",
    })


@staff_member_required
def configuration_hoteliere(request):
    etablissement = obtenir_etablissement_actuel()
    config = getattr(etablissement, "configuration_hoteliere", None) if etablissement else None

    if request.method == "POST":
        form = ConfigurationHoteliereForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, "Configuration hôtelière mise à jour.")
            return redirect("entreprises:configuration_hoteliere")
    else:
        form = ConfigurationHoteliereForm(instance=config)

    return render(request, "entreprises/form.html", {
        "form": form,
        "titre": "Configuration hôtelière",
    })


@staff_member_required
def modules(request):
    entreprise = obtenir_entreprise_actuelle()
    modules_list = ModuleEntreprise.objects.filter(entreprise=entreprise) if entreprise else []

    if request.method == "POST":
        for mod in modules_list:
            actif = request.POST.get(f"module_{mod.id}") == "on"
            if mod.actif != actif:
                mod.actif = actif
                mod.save(update_fields=["actif"])
        messages.success(request, "Modules mis à jour.")
        return redirect("entreprises:modules")

    return render(request, "entreprises/modules.html", {
        "modules": modules_list,
    })


@staff_member_required
def sequences(request):
    entreprise = obtenir_entreprise_actuelle()
    seqs = SequenceDocument.objects.filter(entreprise=entreprise).order_by("type_document") if entreprise else []

    return render(request, "entreprises/sequences.html", {
        "sequences": seqs,
    })

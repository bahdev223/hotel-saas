from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.core.paginator import Paginator
from datetime import date
from ..models import Employe, Departement, Poste
from ..permissions import user_can_gerer_rh
from apps.pos.models import PointVente


@login_required
def liste_employes(request):
    """Liste des employés"""
    if not user_can_gerer_rh(request.user):
        messages.error(request, "Accès réservé au personnel RH.")
        return redirect('dashboard:index')
    employes = Employe.objects.all().order_by('nom', 'prenom')
    
    departement = request.GET.get('departement')
    actif = request.GET.get('actif')
    
    if departement:
        employes = employes.filter(departement__code=departement)
    if actif == 'oui':
        employes = employes.filter(actif=True)
    elif actif == 'non':
        employes = employes.filter(actif=False)
    
    paginator = Paginator(employes, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'employes': page_obj,
        'departements': Departement.objects.filter(actif=True),
        'postes': Poste.objects.all(),
        'groupes': Group.objects.all().order_by('name'),
        'situations': Employe.SITUATION_CHOICES,
        'points_vente': PointVente.objects.filter(actif=True),
        'total': employes.count(),
        'total_actifs': Employe.objects.filter(actif=True).count(),
        'total_hommes': Employe.objects.filter(sexe='M').count(),
        'total_femmes': Employe.objects.filter(sexe='F').count(),
    }
    return render(request, 'rh/employes/liste.html', context)


@login_required
def ajouter_employe(request):
    """Ajouter un employé"""
    if not user_can_gerer_rh(request.user):
        messages.error(request, "Accès réservé au personnel RH.")
        return redirect('dashboard:index')
    if request.method == 'POST':
        try:
            employe = Employe.objects.create(
                nom=request.POST.get('nom'),
                prenom=request.POST.get('prenom'),
                date_naissance=request.POST.get('date_naissance'),
                email=request.POST.get('email'),
                telephone=request.POST.get('telephone'),
                adresse=request.POST.get('adresse'),
                date_embauche=request.POST.get('date_embauche'),
                departement_id=request.POST.get('departement') or None,
                poste_id=request.POST.get('poste') or None,
                situation_familiale=request.POST.get('situation_familiale', 'Celibataire'),
                nombre_enfants=int(request.POST.get('nombre_enfants', 0)),
                conjoint_civilite=request.POST.get('conjoint_civilite', ''),
                conjoint_nom=request.POST.get('conjoint_nom', ''),
                conjoint_prenom=request.POST.get('conjoint_prenom', ''),
                conjoint_contact=request.POST.get('conjoint_contact', ''),
                personne_reference_nom=request.POST.get('personne_reference_nom', ''),
                personne_reference_prenom=request.POST.get('personne_reference_prenom', ''),
                personne_reference_contact=request.POST.get('personne_reference_contact', ''),
                diplome=request.POST.get('diplome', ''),
                description=request.POST.get('description', ''),
                actif=True
            )
            if employe.user:
                groupe_id = request.POST.get('groupe')
                if groupe_id:
                    try:
                        groupe = Group.objects.get(id=int(groupe_id))
                        employe.user.groups.add(groupe)
                    except (Group.DoesNotExist, ValueError, TypeError):
                        pass
            messages.success(request, f'Employé {employe.nom} {employe.prenom} ajouté')
            return redirect('rh:detail_employe', matricule=employe.matricule)
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'departements': Departement.objects.filter(actif=True),
        'postes': Poste.objects.all(),
        'situations': Employe.SITUATION_CHOICES,
        'civilites': Employe.CIVILITE_CHOICES,
    }
    return render(request, 'rh/employes/ajouter.html', context)


@login_required
def detail_employe(request, matricule):
    """Redirige vers la liste des employés (interface dialog)"""
    return redirect('rh:liste_employes')


@login_required
def modifier_employe(request, matricule):
    """Modifier un employé"""
    if not user_can_gerer_rh(request.user):
        messages.error(request, "Accès réservé au personnel RH.")
        return redirect('dashboard:index')
    employe = get_object_or_404(Employe, matricule=matricule)

    if request.method == 'POST':
        try:
            employe.nom = request.POST.get('nom')
            employe.prenom = request.POST.get('prenom')
            employe.date_naissance = request.POST.get('date_naissance')
            employe.email = request.POST.get('email')
            employe.telephone = request.POST.get('telephone')
            employe.adresse = request.POST.get('adresse')
            employe.date_embauche = request.POST.get('date_embauche')
            employe.departement_id = request.POST.get('departement') or None
            employe.poste_id = request.POST.get('poste') or None
            employe.situation_familiale = request.POST.get('situation_familiale', 'Celibataire')
            employe.nombre_enfants = int(request.POST.get('nombre_enfants', 0))
            employe.conjoint_civilite = request.POST.get('conjoint_civilite', '')
            employe.conjoint_nom = request.POST.get('conjoint_nom', '')
            employe.conjoint_prenom = request.POST.get('conjoint_prenom', '')
            employe.conjoint_contact = request.POST.get('conjoint_contact', '')
            employe.personne_reference_nom = request.POST.get('personne_reference_nom', '')
            employe.personne_reference_prenom = request.POST.get('personne_reference_prenom', '')
            employe.personne_reference_contact = request.POST.get('personne_reference_contact', '')
            employe.diplome = request.POST.get('diplome', '')
            employe.description = request.POST.get('description', '')
            employe.actif = request.POST.get('actif') == 'on'
            employe.save()
            
            messages.success(request, 'Employé modifié')
            return redirect('rh:detail_employe', matricule=employe.matricule)
        except Exception as e:
            messages.error(request, str(e))
    
    context = {
        'employe': employe,
        'departements': Departement.objects.filter(actif=True),
        'postes': Poste.objects.all(),
        'situations': Employe.SITUATION_CHOICES,
        'civilites': Employe.CIVILITE_CHOICES,
    }
    return render(request, 'rh/employes/modifier.html', context)


@login_required
def supprimer_employe(request, matricule):
    """Supprimer un employé (soft delete)"""
    if not user_can_gerer_rh(request.user):
        messages.error(request, "Accès réservé au personnel RH.")
        return redirect('dashboard:index')
    employe = get_object_or_404(Employe, matricule=matricule)
    
    if request.method == 'POST':
        employe.actif = False
        employe.date_sortie = date.today()
        employe.save()
        messages.success(request, 'Employé désactivé')
        return redirect('rh:liste_employes')
    
    context = {'employe': employe}
    return render(request, 'rh/employes/supprimer.html', context)



# apps/comptabilite/views/comptes.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from ..models import CompteModel, LigneEcritureModel


def _get_classe_libelle(classe):
    """Retourne le libellé de la classe"""
    libelles = {
        '1': 'RESSOURCES DURABLES (Capital)',
        '2': 'ACTIFS IMMOBILISÉS',
        '3': 'STOCKS',
        '4': 'TIERS',
        '5': 'TRÉSORERIE',
        '6': 'CHARGES',
        '7': 'PRODUITS',
        '8': 'RÉSULTATS',
        '9': 'HORS BILAN'
    }
    return libelles.get(classe, f'Classe {classe}')


# apps/comptabilite/views/comptes.py
from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from ..models import CompteModel


@login_required
def liste_comptes(request):
    """Liste des comptes comptables (pour tableau simple)"""
    
    # 🔥 Récupérer TOUS les comptes
    comptes = CompteModel.objects.filter(actif=True).order_by('code')
    
    print(f"🔍 DEBUG - Nombre de comptes trouvés: {comptes.count()}")  # Vérification
    
    # Filtres
    recherche = request.GET.get('recherche')
    type_compte = request.GET.get('type_compte')
    categorie = request.GET.get('categorie')
    
    if recherche:
        comptes = comptes.filter(
            Q(code__icontains=recherche) | 
            Q(libelle__icontains=recherche)
        )
    if type_compte:
        comptes = comptes.filter(type_compte=type_compte)
    if categorie:
        comptes = comptes.filter(categorie=categorie)
    
    paginator = Paginator(comptes, 50)
    page = request.GET.get('page')
    page_obj = paginator.get_page(page)
    
    # Statistiques
    stats = {
        'total': CompteModel.objects.filter(actif=True).count(),
        'standard': CompteModel.objects.filter(actif=True, type_compte__in=['classe', 'groupe', 'compte']).count(),
        'personnalises': CompteModel.objects.filter(actif=True, type_compte='sous_compte').count(),
    }
    
    context = {
        'comptes': page_obj,  # ← La clé doit être 'comptes'
        'stats': stats,
        'recherche': recherche,
        'type_compte': type_compte,
        'categorie': categorie,
        'types_compte': CompteModel.TYPE_CHOICES,
        'categories': CompteModel.CATEGORIE_CHOICES,
    }
    return render(request, 'comptabilite/comptes/liste.html', context)
@login_required
def ajouter_compte(request):
    """Ajouter un sous-compte personnalisé (non standard)"""
    
    if request.method == 'POST':
        try:
            code = request.POST.get('code')
            libelle = request.POST.get('libelle')
            parent_id = request.POST.get('parent')
            
            if not code or not libelle or not parent_id:
                messages.error(request, 'Tous les champs sont obligatoires')
                return redirect('comptabilite:ajouter_compte')
            
            if CompteModel.objects.filter(code=code).exists():
                messages.error(request, f'Le code {code} existe déjà')
                return redirect('comptabilite:ajouter_compte')
            
            parent = get_object_or_404(CompteModel, id=parent_id)
            
            if parent.type_compte not in ['compte', 'sous_compte']:
                messages.error(request, 'Vous ne pouvez créer un sous-compte que sous un compte standard')
                return redirect('comptabilite:ajouter_compte')
            
            compte = CompteModel.objects.create(
                code=code,
                libelle=libelle,
                nature=parent.nature,
                sens=parent.sens,
                parent=parent,
                niveau=parent.niveau + 1,
                type_compte='sous_compte',
                est_mouvement=True,
                categorie=parent.categorie,
                actif=True
            )
            
            messages.success(request, f'Compte {compte.code} - {compte.libelle} créé')
            return redirect('comptabilite:liste_comptes')
            
        except Exception as e:
            messages.error(request, str(e))
    
    parents = CompteModel.objects.filter(
        actif=True,
        type_compte__in=['compte', 'sous_compte'],
        est_mouvement=True
    ).order_by('code')
    
    context = {
        'parents': parents,
        'types_compte': CompteModel.TYPE_CHOICES,
        'categories': CompteModel.CATEGORIE_CHOICES,
    }
    return render(request, 'comptabilite/comptes/ajouter.html', context)


@login_required
def modifier_compte(request, compte_id):
    """Modifier un compte personnalisé (seulement les sous-comptes)"""
    
    compte = get_object_or_404(CompteModel, id=compte_id)
    
    if compte.type_compte not in ['sous_compte']:
        messages.error(request, 'Les comptes standards ne peuvent pas être modifiés')
        return redirect('comptabilite:liste_comptes')
    
    if request.method == 'POST':
        try:
            compte.libelle = request.POST.get('libelle')
            compte.actif = request.POST.get('actif') == 'on'
            compte.save()
            
            messages.success(request, f'Compte {compte.code} modifié')
            return redirect('comptabilite:liste_comptes')
            
        except Exception as e:
            messages.error(request, str(e))
    
    context = {'compte': compte}
    return render(request, 'comptabilite/comptes/modifier.html', context)


@login_required
def detail_compte(request, compte_id):
    """Détail d'un compte comptable avec ses sous-comptes"""
    
    compte = get_object_or_404(CompteModel, id=compte_id)
    enfants = compte.enfants.filter(actif=True).order_by('code')
    
    context = {
        'compte': compte,
        'enfants': enfants,
    }
    return render(request, 'comptabilite/comptes/detail.html', context)


def calculer_solde_compte(compte, exercice):
    """Calcule le solde d'un compte (fonction utilitaire)"""
    lignes = LigneEcritureModel.objects.filter(
        compte=compte,
        ecriture__exercice=exercice
    )
    
    total_debit = sum(l.debit for l in lignes)
    total_credit = sum(l.credit for l in lignes)
    
    if compte.nature in ['ACTIF', 'CHARGE']:
        return total_debit - total_credit
    else:
        return total_credit - total_debit
    
    
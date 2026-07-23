from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from ..models import Employe


@login_required
def dashboard(request):
    """Dashboard RH"""
    employes = Employe.objects.all()
    
    # Calcul de la masse salariale
    masse_salariale = employes.filter(actif=True).aggregate(total=Sum('salaire_fixe'))['total'] or 0
    
    # Salaire moyen
    employes_actifs = employes.filter(actif=True)
    total_actifs = employes_actifs.count()
    salaire_moyen = masse_salariale / total_actifs if total_actifs > 0 else 0
    
    # Répartition par département
    departements = {}
    for dept in employes.filter(departement__isnull=False).values('departement__libelle').annotate(total=Count('id')):
        departements[dept['departement__libelle']] = dept['total']
    
    # Répartition par poste
    postes = {}
    for p in employes.filter(poste__isnull=False).values('poste__intitule').annotate(total=Count('id')):
        postes[p['poste__intitule']] = p['total']
    
    context = {
        # Infos employés
        'total_employes': employes.count(),
        'employes_actifs': total_actifs,
        'employes_inactifs': employes.filter(actif=False).count(),
        'hommes': employes.filter(sexe='M').count(),
        'femmes': employes.filter(sexe='F').count(),
        
        # Masse salariale
        'masse_salariale': masse_salariale,
        'salaire_moyen': salaire_moyen,
        
        # Répartition départements
        'departements': departements,
        'postes': postes,
        
        # Derniers employés
        'derniers_employes': employes.exclude(matricule='').exclude(matricule__isnull=True).order_by('-created_at')[:10],
    }
    return render(request, 'rh/dashboard.html', context)


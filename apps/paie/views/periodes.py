from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import date
from ..models import PeriodePaie


@login_required
def liste_periodes(request):
    """ Liste des périodes """
    periodes = PeriodePaie.objects.all()
    return render(request, 'paie/periodes/liste.html', {'periodes': periodes})


@login_required
def creer_periode(request):
    """ Créer une nouvelle période """
    if request.method == 'POST':
        annee = int(request.POST.get('annee'))
        mois = int(request.POST.get('mois'))
        
        if PeriodePaie.objects.filter(annee=annee, mois=mois).exists():
            messages.error(request, "Cette période existe déjà")
            return redirect('paie:liste_periodes')
        
        # Calculer dates début et fin
        date_debut = date(annee, mois, 1)
        if mois == 12:
            date_fin = date(annee + 1, 1, 1)
        else:
            date_fin = date(annee, mois + 1, 1)
        
        from datetime import timedelta
        date_fin = date_fin - timedelta(days=1)
        
        PeriodePaie.objects.create(
            annee=annee,
            mois=mois,
            date_debut=date_debut,
            date_fin=date_fin
        )
        
        messages.success(request, f"Période {mois:02d}/{annee} créée")
        return redirect('paie:liste_periodes')
    
    return render(request, 'paie/periodes/creer.html')

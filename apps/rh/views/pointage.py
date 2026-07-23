from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from datetime import date
import uuid
from ..models import Pointage, Employe


@login_required
def pointage(request):
    """Pointage des employés"""
    pointages = Pointage.objects.filter(date_pointage=date.today()).select_related('employe')
    
    if request.method == 'POST':
        try:
            Pointage.objects.create(
                id_pointage=f"PT-{uuid.uuid4().hex[:8].upper()}",
                employe_id=request.POST.get('employe_id'),
                date_pointage=date.today(),
                heure_entree=request.POST.get('heure_entree'),
                heure_sortie=request.POST.get('heure_sortie'),
                commentaire=request.POST.get('commentaire', '')
            )
            messages.success(request, 'Pointage enregistré')
            return redirect('rh:pointage')
        except Exception as e:
            messages.error(request, str(e))
    
    employes = Employe.objects.filter(actif=True)
    return render(request, 'rh/pointage.html', {'pointages': pointages, 'employes': employes})


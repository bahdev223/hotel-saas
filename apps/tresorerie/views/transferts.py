from django.shortcuts import redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from ..models import Caisse
from ..services import TransfertService


@login_required
def transfert_caisse(request):
    if request.method == 'POST':
        try:
            source_id = request.POST.get('source_id')
            dest_id = request.POST.get('dest_id')
            montant = float(request.POST.get('montant', 0))
            notes = request.POST.get('notes', '')

            source = Caisse.objects.get(id=source_id, actif=True)
            destination = Caisse.objects.get(id=dest_id, actif=True)
            TransfertService.transferer(source, destination, montant, request.user, notes)
            messages.success(request, f'Transfert de {montant:,.0f} F effectué')
        except Exception as e:
            messages.error(request, str(e))
    return redirect('tresorerie:dashboard_tresorier')


@login_required
def liste_transferts(request):
    return redirect('tresorerie:dashboard_tresorier')

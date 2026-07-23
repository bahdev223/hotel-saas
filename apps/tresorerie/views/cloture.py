from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from ..models import Caisse


@login_required
def cloturer_caisse(request, caisse_id):
    caisse = get_object_or_404(Caisse, id=caisse_id)
    if request.method == 'POST':
        try:
            from ..services import ClotureService
            ClotureService.cloturer_journal(caisse, request.user)
            messages.success(request, f'Caisse {caisse.nom} clôturée')
        except Exception as e:
            messages.error(request, str(e))
    return redirect('tresorerie:dashboard_tresorier')

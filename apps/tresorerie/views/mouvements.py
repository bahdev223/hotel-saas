from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def liste_mouvements(request):
    return redirect('tresorerie:dashboard_tresorier')

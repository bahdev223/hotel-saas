import json
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from apps.stock.models import Domaine
from apps.authentication.groups import PATRON, MANAGER, STOCK, BAR, RESTAURANT, CAISSIER, RAF

ALLOWED_GROUPS = [PATRON, MANAGER, STOCK, BAR, RESTAURANT, CAISSIER, RAF]


@login_required
def index(request):
    user_groups = request.user.groups.values_list('name', flat=True)
    if not any(g in ALLOWED_GROUPS for g in user_groups):
        messages.error(request, "Acces refuse.")
        return redirect('admin:index')

    domaines = list(Domaine.objects.filter(actif=True).values('id', 'nom', 'icone'))

    return render(request, 'catalogue/index.html', {
        'domaines_json': json.dumps(domaines, ensure_ascii=False),
    })






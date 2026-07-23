# apps/stock/views/fournisseurs.py
# Redirigé vers apps.fournisseurs
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required


@login_required
def liste_fournisseurs(request):
    return redirect('fournisseurs:dashboard')


@login_required
def detail_fournisseur(request, fournisseur_id):
    return redirect('fournisseurs:detail', fournisseur_id=fournisseur_id)


# Legacy API support
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from ..models import Fournisseur
from apps.comptabilite.models import CompteFournisseur
from decimal import Decimal
import json


@require_http_methods(["GET"])
@login_required
def api_liste_fournisseurs(request):
    qs = Fournisseur.objects.filter(actif=True).order_by('nom')
    data = [{'id': f.id, 'code': f.code, 'nom': f.nom} for f in qs]
    return JsonResponse(data, safe=False)


@require_http_methods(["GET"])
@login_required
def api_detail_fournisseur(request, fournisseur_id):
    f = Fournisseur.objects.get(id=fournisseur_id)
    compte = CompteFournisseur.objects.filter(fournisseur=f).first()
    return JsonResponse({
        'id': f.id, 'code': f.code, 'nom': f.nom,
        'telephone': f.telephone, 'email': f.email,
        'adresse': f.adresse, 'contact': f.contact,
        'identifiant_fiscal': f.identifiant_fiscal,
        'solde': float(compte.solde) if compte else 0,
    })

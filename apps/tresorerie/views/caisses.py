from django.shortcuts import redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required

from ..models import Caisse
from ..services import ClotureService
from ..services.compte_financier_service import CompteFinancierService


@login_required
def liste_caisses(request):
    return redirect('tresorerie:dashboard_tresorier')


@login_required
def detail_caisse(request, caisse_id):
    return redirect('tresorerie:dashboard_tresorier')


@login_required
def ajouter_caisse(request):
    if request.method == 'POST':
        try:
            nom = request.POST.get('nom')
            type_financier = request.POST.get('type_financier', 'ESPECES')
            role = request.POST.get('role') or None
            actif = request.POST.get('actif') == 'on'

            prefixe = 'CMPT'
            dernier = Caisse.objects.filter(code__startswith=prefixe).order_by('code').last()
            if dernier:
                try:
                    num = int(dernier.code.replace(prefixe + '-', '')) + 1
                except ValueError:
                    num = Caisse.objects.count() + 1
            else:
                num = 1
            code = f"{prefixe}-{num:03d}"

            caisse = Caisse.objects.create(
                code=code, nom=nom,
                type_financier=type_financier, role=role,
                actif=actif
            )
            caisse.compte_comptable = CompteFinancierService.generer_compte_comptable(caisse)
            caisse.full_clean()
            caisse.save(update_fields=['compte_comptable'])
            messages.success(request, f'"{nom}" créé (code: {code})')
        except Exception as e:
            messages.error(request, str(e))
    return redirect('tresorerie:dashboard_tresorier')


@login_required
def modifier_caisse(request, caisse_id):
    caisse = get_object_or_404(Caisse, id=caisse_id)
    if request.method == 'POST':
        try:
            caisse.nom = request.POST.get('nom')
            caisse.type_financier = request.POST.get('type_financier')
            caisse.role = request.POST.get('role') or None
            caisse.actif = request.POST.get('actif') == 'on'

            ancien_compte = caisse.compte_comptable
            caisse.compte_comptable = CompteFinancierService.generer_compte_comptable(caisse)
            if ancien_compte and ancien_compte != caisse.compte_comptable:
                pass
            caisse.full_clean()
            caisse.save()
            messages.success(request, f'Compte "{caisse.nom}" modifié')
        except Exception as e:
            messages.error(request, str(e))
    return redirect('tresorerie:dashboard_tresorier')


@login_required
def supprimer_caisse(request, caisse_id):
    caisse = get_object_or_404(Caisse, id=caisse_id)
    if request.method == 'POST':
        nom = caisse.nom
        caisse.delete()
        messages.success(request, f'Compte "{nom}" supprimé')
    return redirect('tresorerie:dashboard_tresorier')

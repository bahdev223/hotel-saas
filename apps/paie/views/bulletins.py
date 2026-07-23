from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from ..models import BulletinPaie, PeriodePaie
from ..services.paie_service import PaieService


@login_required
def liste_bulletins(request):
    """ Liste des bulletins """
    bulletins = BulletinPaie.objects.all().select_related('employe', 'periode')
    periode_id = request.GET.get('periode')
    
    if periode_id:
        bulletins = bulletins.filter(periode_id=periode_id)
    
    periodes = PeriodePaie.objects.all()
    
    context = {
        'bulletins': bulletins,
        'periodes': periodes,
        'periode_selected': periode_id,
        'total_net': sum(b.net_a_payer for b in bulletins),
    }
    return render(request, 'paie/bulletins/liste.html', context)


@login_required
def detail_bulletin(request, bulletin_id):
    """ Détail d'un bulletin """
    bulletin = get_object_or_404(BulletinPaie, id=bulletin_id)
    lignes = bulletin.lignes.all().select_related('rubrique')
    
    context = {
        'bulletin': bulletin,
        'lignes': lignes,
    }
    return render(request, 'paie/bulletins/detail.html', context)


@login_required
def generer_bulletins(request, periode_id):
    """ Générer les bulletins pour une période """
    periode = get_object_or_404(PeriodePaie, id=periode_id)
    
    if request.method == 'POST':
        resultats = PaieService.generer_tous_bulletins(periode_id)
        success = sum(1 for r in resultats if r['success'])
        errors = len(resultats) - success
        
        if success > 0:
            messages.success(request, f"{success} bulletins générés avec succès")
        if errors > 0:
            messages.warning(request, f"{errors} bulletins en erreur")
        
        return redirect('paie:liste_bulletins')
    
    context = {'periode': periode}
    return render(request, 'paie/bulletins/generer.html', context)


@login_required
def valider_bulletin(request, bulletin_id):
    """ Valider un bulletin """
    bulletin = get_object_or_404(BulletinPaie, id=bulletin_id)
    
    if request.method == 'POST':
        bulletin.statut = 'VALIDE'
        bulletin.save()
        messages.success(request, "Bulletin validé avec succès")
        return redirect('paie:detail_bulletin', bulletin_id=bulletin.id)
    
    context = {'bulletin': bulletin}
    return render(request, 'paie/bulletins/valider.html', context)

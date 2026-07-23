from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Sum
from .models import Fournisseur
from apps.comptabilite.models import CompteFournisseur, CompteModel


@login_required
def dashboard(request):
    fournisseurs = Fournisseur.objects.filter(actif=True).order_by('nom')
    total = fournisseurs.count()
    total_dette = CompteFournisseur.objects.filter(
        fournisseur__actif=True
    ).aggregate(s=Sum('solde'))['s'] or 0
    context = {
        'fournisseurs': fournisseurs,
        'total': total,
        'total_dette': float(total_dette),
        'titre': 'Fournisseurs — Tableau de bord',
    }
    return render(request, 'fournisseurs/dashboard.html', context)


@login_required
def detail(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    comptes = CompteFournisseur.objects.filter(
        fournisseur=fournisseur
    ).select_related('exercice').order_by('-exercice__date_debut')
    solde_actuel = comptes.first().solde if comptes else 0
    context = {
        'fournisseur': fournisseur,
        'comptes': comptes,
        'solde_actuel': float(solde_actuel),
        'titre': f'{fournisseur.nom} — Fournisseur',
    }
    return render(request, 'fournisseurs/detail.html', context)


@login_required
def ajouter(request):
    if request.method == 'POST':
        try:
            code = request.POST.get('code', '').strip()
            if not code:
                code = f"FR-{uuid.uuid4().hex[:6].upper()}"
            compte_id = request.POST.get('compte_comptable_id')
            compte = CompteModel.objects.filter(id=compte_id).first() if compte_id else None
            Fournisseur.objects.create(
                code=code,
                nom=request.POST.get('nom'),
                telephone=request.POST.get('telephone', ''),
                email=request.POST.get('email', ''),
                adresse=request.POST.get('adresse', ''),
                contact=request.POST.get('contact', ''),
                identifiant_fiscal=request.POST.get('identifiant_fiscal', ''),
                notes=request.POST.get('notes', ''),
                compte_comptable=compte,
                actif=True,
            )
            messages.success(request, 'Fournisseur ajouté avec succès')
            return redirect('fournisseurs:dashboard')
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    comptes = CompteModel.objects.filter(
        actif=True, type_compte__in=['compte', 'sous_compte']
    ).order_by('code')
    return render(request, 'fournisseurs/ajouter.html', {'comptes_comptables': comptes})


@login_required
def modifier(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    if request.method == 'POST':
        try:
            fournisseur.nom = request.POST.get('nom')
            fournisseur.telephone = request.POST.get('telephone', '')
            fournisseur.email = request.POST.get('email', '')
            fournisseur.adresse = request.POST.get('adresse', '')
            fournisseur.contact = request.POST.get('contact', '')
            fournisseur.identifiant_fiscal = request.POST.get('identifiant_fiscal', '')
            fournisseur.notes = request.POST.get('notes', '')
            compte_id = request.POST.get('compte_comptable_id')
            if compte_id:
                fournisseur.compte_comptable = CompteModel.objects.get(id=compte_id)
            else:
                fournisseur.compte_comptable = None
            fournisseur.save()
            messages.success(request, 'Fournisseur modifié avec succès')
            return redirect('fournisseurs:detail', fournisseur_id=fournisseur.id)
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')
    comptes = CompteModel.objects.filter(
        actif=True, type_compte__in=['compte', 'sous_compte']
    ).order_by('code')
    return render(request, 'fournisseurs/modifier.html', {
        'fournisseur': fournisseur,
        'comptes_comptables': comptes,
    })


@login_required
def supprimer(request, fournisseur_id):
    fournisseur = get_object_or_404(Fournisseur, id=fournisseur_id)
    if request.method == 'POST':
        fournisseur.actif = False
        fournisseur.save()
        messages.success(request, f'Fournisseur {fournisseur.nom} désactivé')
        return redirect('fournisseurs:dashboard')
    return render(request, 'fournisseurs/supprimer.html', {'fournisseur': fournisseur})


import uuid


# --- API ---

@login_required
def api_liste(request):
    fournisseurs = Fournisseur.objects.filter(actif=True).order_by('nom')
    search = request.GET.get('search')
    if search:
        fournisseurs = fournisseurs.filter(
            Q(nom__icontains=search) | Q(code__icontains=search) |
            Q(telephone__icontains=search)
        )
    data = []
    for f in fournisseurs:
        compte = f.comptes.order_by('-exercice__date_debut').first()
        data.append({
            'id': f.id,
            'code': f.code,
            'nom': f.nom,
            'telephone': f.telephone or '',
            'email': f.email or '',
            'contact': f.contact or '',
            'identifiant_fiscal': f.identifiant_fiscal or '',
            'solde': float(compte.solde) if compte else 0,
        })
    return JsonResponse({'success': True, 'fournisseurs': data})


@login_required
def api_detail(request, fournisseur_id):
    f = get_object_or_404(Fournisseur, id=fournisseur_id)
    comptes = CompteFournisseur.objects.filter(fournisseur=f).select_related('exercice')
    return JsonResponse({
        'success': True,
        'fournisseur': {
            'id': f.id,
            'code': f.code,
            'nom': f.nom,
            'telephone': f.telephone or '',
            'email': f.email or '',
            'adresse': f.adresse or '',
            'contact': f.contact or '',
            'identifiant_fiscal': f.identifiant_fiscal or '',
            'notes': f.notes or '',
            'actif': f.actif,
            'compte_comptable_id': f.compte_comptable_id,
            'compte_comptable': f.compte_comptable.libelle if f.compte_comptable else None,
        },
        'comptes': [
            {
                'exercice': c.exercice.code,
                'solde': float(c.solde),
                'ecart_lettrage': float(c.ecart_lettrage),
            }
            for c in comptes
        ],
    })

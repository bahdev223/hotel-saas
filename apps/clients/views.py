from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Q, Sum

from .models import Client
from datetime import date
from apps.comptabilite.models import CompteClient
from apps.comptabilite.services.ecriture_comptable import EcritureComptableService


@login_required
def dashboard(request):
    clients = Client.objects.exclude(id=Client.PASSAGER_ID)
    total_clients = clients.count()
    actifs = clients.filter(statut='ACTIF').count()

    stats_par_type = {}
    for type_value, _ in Client.TYPE_CLIENT_CHOICES:
        stats_par_type[type_value] = clients.filter(type_client=type_value).count()

    stats_par_statut = {}
    for statut_value, _ in Client.STATUT_CHOICES:
        stats_par_statut[statut_value] = clients.filter(statut=statut_value).count()

    context = {
        'total_clients': total_clients,
        'actifs': actifs,
        'stats_par_type': stats_par_type,
        'stats_par_statut': stats_par_statut,
        'clients_recents': clients.order_by('-created_at')[:5],
    }
    return render(request, 'clients/dashboard.html', context)


@login_required
def ajouter_client(request):
    if request.method == 'POST':
        try:
            client = Client.objects.create(
                nom=request.POST.get('nom'),
                prenom=request.POST.get('prenom', ''),
                telephone=request.POST.get('telephone', ''),
                email=request.POST.get('email', ''),
                adresse=request.POST.get('adresse', ''),
                type_client=request.POST.get('type_client', 'PARTICULIER'),
                statut='ACTIF',
            )

            solde_initial = request.POST.get('solde_initial', '').strip()
            if solde_initial:
                from decimal import Decimal
                from datetime import date
                from apps.comptabilite.models import CompteClient
                from apps.comptabilite.services.ecriture_comptable import EcritureComptableService
                montant = Decimal(solde_initial)
                if montant != 0:
                    exercice = EcritureComptableService._get_exercice(date.today())
                    CompteClient.objects.create(
                        client=client,
                        exercice=exercice,
                        solde=montant,
                    )

            messages.success(request, f'Client {client.nom_complet} ajouté avec succès')
            return redirect('clients:dashboard')
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    types_client = [t[0] for t in Client.TYPE_CLIENT_CHOICES]
    return render(request, 'clients/ajouter.html', {'types_client': types_client})


@login_required
def detail_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    exercice = EcritureComptableService._get_exercice(date.today())
    compte_client = CompteClient.objects.filter(client=client, exercice=exercice).first()
    solde_actuel = float(compte_client.solde) if compte_client else 0
    return render(request, 'clients/detail.html', {
        'client': client,
        'solde_actuel': solde_actuel,
        'compte_client': compte_client,
    })


@login_required
def modifier_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    if request.method == 'POST':
        try:
            client.nom = request.POST.get('nom')
            client.prenom = request.POST.get('prenom', '')
            client.telephone = request.POST.get('telephone', '')
            client.email = request.POST.get('email', '')
            client.adresse = request.POST.get('adresse', '')
            client.type_client = request.POST.get('type_client')
            client.save()
            messages.success(request, 'Client modifié avec succès')
            return redirect('clients:dashboard')
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    types_client = [t[0] for t in Client.TYPE_CLIENT_CHOICES]
    return render(request, 'clients/modifier.html', {
        'client': client,
        'types_client': types_client
    })


@login_required
def api_liste_clients(request):
    clients = Client.objects.exclude(id=Client.PASSAGER_ID)
    type_filter = request.GET.get('type')
    statut_filter = request.GET.get('statut')
    search_term = request.GET.get('search')

    if type_filter:
        clients = clients.filter(type_client=type_filter)
    if statut_filter:
        clients = clients.filter(statut=statut_filter)
    if search_term:
        clients = clients.filter(
            Q(nom__icontains=search_term) |
            Q(prenom__icontains=search_term) |
            Q(telephone__icontains=search_term) |
            Q(id__icontains=search_term)
        )

    data = []
    for c in clients.order_by('-created_at')[:100]:
        compte = c.comptes.order_by('-exercice__date_debut').first()
        data.append({
            'id': c.id,
            'nom_complet': c.nom_complet,
            'nom': c.nom,
            'prenom': c.prenom,
            'telephone': c.telephone or '',
            'email': c.email or '',
            'adresse': c.adresse or '',
            'type_client': c.type_client,
            'type_client_display': c.get_type_client_display(),
            'statut': c.statut,
            'statut_display': c.get_statut_display(),
            'solde': float(compte.solde) if compte else 0,
            'date_inscription': c.date_inscription.isoformat() if c.date_inscription else '',
        })
    return JsonResponse({'success': True, 'clients': data})


from apps.clients.services.client_detail_service import get_client_operations, get_client_solde_movements


@login_required
def api_detail_client(request, client_id):
    """API renvoyant toutes les operations + mouvements de solde d'un client."""
    client = get_object_or_404(Client, id=client_id)
    operations = get_client_operations(client_id)
    solde = get_client_solde_movements(client_id)

    return JsonResponse({
        'success': True,
        'client': {
            'id': client.id,
            'nom_complet': client.nom_complet,
            'nom': client.nom,
            'prenom': client.prenom,
            'telephone': client.telephone or '',
            'email': client.email or '',
            'adresse': client.adresse or '',
            'type_client': client.type_client,
            'type_client_display': client.get_type_client_display(),
            'statut': client.statut,
            'statut_display': client.get_statut_display(),
            'date_inscription': client.date_inscription.isoformat() if client.date_inscription else '',
            'notes': client.notes or '',
            'identifiant_fiscal': client.identifiant_fiscal or '',
            'credit_plafond': float(client.credit_plafond) if client.credit_plafond else 0,
        },
        'operations': operations,
        'solde': solde,
    })


@login_required
def supprimer_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    solde_total = CompteClient.objects.filter(client=client).aggregate(
        total=Sum('solde')
    )['total'] or 0

    if request.method == 'POST':
        if solde_total != 0:
            messages.error(
                request,
                f"Impossible de supprimer {client.nom_complet} : solde non nul "
                f"({solde_total:,.0f} F). Désactivez le client au lieu de le supprimer."
            )
            return redirect('clients:supprimer', client_id=client.id)
        client.delete()
        messages.success(request, 'Client supprimé')
        return redirect('clients:dashboard')

    return render(request, 'clients/supprimer.html', {'client': client, 'solde_total': solde_total})


@login_required
def changer_statut(request, client_id):
    if request.method == 'POST':
        nouveau_statut = request.POST.get('statut')
        valid_statuts = [s[0] for s in Client.STATUT_CHOICES]
        if nouveau_statut in valid_statuts:
            Client.objects.filter(id=client_id).update(statut=nouveau_statut)
            messages.success(request, f'Statut modifié: {dict(Client.STATUT_CHOICES).get(nouveau_statut)}')
        else:
            messages.error(request, 'Statut invalide')
    return redirect('clients:dashboard')

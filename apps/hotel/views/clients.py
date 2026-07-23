from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q

from apps.clients.models import Client


@login_required
def liste_clients(request):
    clients = Client.objects.filter(statut='ACTIF').order_by('nom', 'prenom')

    search = request.GET.get('search')
    if search:
        clients = clients.filter(
            Q(nom__icontains=search) |
            Q(prenom__icontains=search) |
            Q(telephone__icontains=search) |
            Q(email__icontains=search)
        )

    paginator = Paginator(clients, 30)
    page = request.GET.get('page')
    clients_page = paginator.get_page(page)

    context = {
        'clients': clients_page,
        'search': search,
    }
    return render(request, 'hotel/clients/liste.html', context)


@login_required
def detail_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    locations = client.locations.all().select_related('unite').order_by('-created_at')[:20]

    context = {
        'client': client,
        'locations': locations,
    }
    return render(request, 'hotel/clients/detail.html', context)


@login_required
def ajouter_client(request):
    if request.method == 'POST':
        try:
            client = Client.objects.create(
                nom=request.POST.get('nom'),
                prenom=request.POST.get('prenom'),
                email=request.POST.get('email') or None,
                telephone=request.POST.get('telephone'),
                adresse=request.POST.get('adresse', ''),
                sexe=request.POST.get('sexe') or None,
                date_naissance=request.POST.get('date_naissance') or None,
                piece_identite=request.POST.get('piece_identite'),
                numero_piece=request.POST.get('numero_piece'),
                notes=request.POST.get('notes', ''),
            )
            messages.success(request, f'Client {client.nom_complet} ajouté')
            return redirect('hotel:detail_client', client_id=client.id)
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    context = {
        'sexe_choices': Client.SEXE_CHOICES,
    }
    return render(request, 'hotel/clients/ajouter.html', context)


@login_required
def modifier_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    if request.method == 'POST':
        try:
            client.nom = request.POST.get('nom')
            client.prenom = request.POST.get('prenom')
            client.email = request.POST.get('email') or None
            client.telephone = request.POST.get('telephone')
            client.adresse = request.POST.get('adresse', '')
            client.sexe = request.POST.get('sexe') or None
            client.date_naissance = request.POST.get('date_naissance') or None
            client.piece_identite = request.POST.get('piece_identite')
            client.numero_piece = request.POST.get('numero_piece')
            client.notes = request.POST.get('notes', '')
            client.save()
            messages.success(request, f'Client {client.nom_complet} modifié')
            return redirect('hotel:detail_client', client_id=client.id)
        except Exception as e:
            messages.error(request, f'Erreur: {str(e)}')

    context = {
        'client': client,
        'sexe_choices': Client.SEXE_CHOICES,
    }
    return render(request, 'hotel/clients/modifier.html', context)

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
    """Page liste dédiée des clients : stats + tableau filtrable paginé
    (server-side). Chaque ligne mène à la fiche client 360°."""
    from django.core.paginator import Paginator
    from django.db.models import Sum

    base = Client.objects.exclude(id=Client.PASSAGER_ID)

    # Stats globales (sur l'ensemble, indépendamment des filtres)
    total_clients = base.count()
    actifs = base.filter(statut='ACTIF').count()
    entreprises = base.filter(type_client='ENTREPRISE').count()
    agences = base.filter(type_client='AGENCE').count()

    # Filtres
    q = request.GET.get('q', '').strip()
    type_filter = request.GET.get('type', '')
    statut_filter = request.GET.get('statut', '')

    clients = base
    if q:
        clients = clients.filter(
            Q(nom__icontains=q) | Q(prenom__icontains=q)
            | Q(telephone__icontains=q) | Q(email__icontains=q) | Q(id__icontains=q)
        )
    if type_filter:
        clients = clients.filter(type_client=type_filter)
    if statut_filter:
        clients = clients.filter(statut=statut_filter)

    clients = clients.annotate(solde_total=Sum('comptes__solde')).order_by('nom', 'prenom')

    paginator = Paginator(clients, 30)
    page = paginator.get_page(request.GET.get('page'))

    context = {
        'total_clients': total_clients,
        'actifs': actifs,
        'entreprises': entreprises,
        'agences': agences,
        'clients': page,
        'total_resultats': paginator.count,
        'types_client': Client.TYPE_CLIENT_CHOICES,
        'statuts': Client.STATUT_CHOICES,
        'f': {'q': q, 'type': type_filter, 'statut': statut_filter},
    }
    return render(request, 'clients/liste.html', context)


def _is_ajax(request):
    return request.headers.get('X-Requested-With') == 'XMLHttpRequest'


@login_required
def ajouter_client(request):
    est_dialogue = request.headers.get("HX-Target") == "modal"

    if request.method == 'POST':
        nom = (request.POST.get('nom') or '').strip()
        telephone = (request.POST.get('telephone') or '').strip()
        if not nom or not telephone:
            erreur = 'Le nom et le téléphone sont obligatoires.'
            if est_dialogue:
                messages.error(request, erreur)
                return render(request, 'clients/_dialog_ajouter.html', {
                    'types_client': [t[0] for t in Client.TYPE_CLIENT_CHOICES],
                })
            if _is_ajax(request):
                return JsonResponse({'success': False, 'error': erreur}, status=400)
            messages.error(request, erreur)
            return render(request, 'clients/ajouter.html', {
                'types_client': [t[0] for t in Client.TYPE_CLIENT_CHOICES],
            })
        try:
            client = Client.objects.create(
                nom=nom,
                prenom=request.POST.get('prenom', ''),
                telephone=telephone,
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

            if est_dialogue:
                messages.success(request, f'Client {client.nom_complet} ajouté avec succès')
                return render(request, 'clients/_dialog_ajouter.html', {'succes': True, 'unite': client})
            if _is_ajax(request):
                return JsonResponse({'success': True, 'id': client.id})
            messages.success(request, f'Client {client.nom_complet} ajouté avec succès')
            return redirect('clients:dashboard')
        except Exception as e:
            if est_dialogue:
                messages.error(request, f'Erreur: {str(e)}')
                return render(request, 'clients/_dialog_ajouter.html', {
                    'types_client': [t[0] for t in Client.TYPE_CLIENT_CHOICES],
                })
            if _is_ajax(request):
                return JsonResponse({'success': False, 'error': str(e)}, status=400)
            messages.error(request, f'Erreur: {str(e)}')

    types_client = [t[0] for t in Client.TYPE_CLIENT_CHOICES]
    if est_dialogue:
        return render(request, 'clients/_dialog_ajouter.html', {'types_client': types_client})
    return render(request, 'clients/ajouter.html', {'types_client': types_client})


@login_required
def detail_client(request, client_id):
    """Fiche client 360° : identité, position financière canonique,
    indicateurs commerciaux, chronologie unifiée et opérations détaillées."""
    from apps.clients.services.client_account_service import ClientAccountService
    from apps.clients.services.client_timeline_service import ClientTimelineService
    from apps.clients.services.client_detail_service import get_client_operations

    client = get_object_or_404(Client, id=client_id)
    position = ClientAccountService.get_position(client_id)
    indicateurs = ClientTimelineService.get_indicateurs(client_id)
    timeline = ClientTimelineService.get_timeline(client_id, limit=100)
    operations = get_client_operations(client_id)

    return render(request, 'clients/detail.html', {
        'client': client,
        'position': position,
        'indicateurs': indicateurs,
        'timeline': timeline,
        'operations': operations,
    })


@login_required
def modifier_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)

    if request.method == 'POST':
        nom = (request.POST.get('nom') or '').strip()
        telephone = (request.POST.get('telephone') or '').strip()
        if not nom or not telephone:
            erreur = 'Le nom et le téléphone sont obligatoires.'
            if _is_ajax(request):
                return JsonResponse({'success': False, 'error': erreur}, status=400)
            messages.error(request, erreur)
        else:
            try:
                client.nom = nom
                client.prenom = request.POST.get('prenom', '')
                client.telephone = telephone
                client.email = request.POST.get('email', '')
                client.adresse = request.POST.get('adresse', '')
                client.type_client = request.POST.get('type_client') or client.type_client
                client.save()
                if _is_ajax(request):
                    return JsonResponse({'success': True})
                messages.success(request, 'Client modifié avec succès')
                return redirect('clients:dashboard')
            except Exception as e:
                if _is_ajax(request):
                    return JsonResponse({'success': False, 'error': str(e)}, status=400)
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


def _client_a_des_operations(client):
    """True si le client possède la moindre opération métier.
    Un tel client ne doit JAMAIS être supprimé physiquement (l'historique
    séjours/ventes/factures serait détruit ou orphelin) : on le désactive."""
    from apps.hotel.models import LocationModel, Reservation, Sejour
    from apps.pos.models import Commande, Vente
    from apps.facturation.models import FactureModel
    from apps.paiements.models import Paiement

    verifications = (
        Reservation.objects.filter(client=client),
        Sejour.objects.filter(client=client),
        LocationModel.objects.filter(client=client),
        Commande.objects.filter(client=client),
        Vente.objects.filter(client=client),
        FactureModel.objects.filter(client=client),
        Paiement.objects.filter(client=client),
    )
    return any(qs.exists() for qs in verifications)


@login_required
def supprimer_client(request, client_id):
    client = get_object_or_404(Client, id=client_id)
    solde_total = CompteClient.objects.filter(client=client).aggregate(
        total=Sum('solde')
    )['total'] or 0
    a_operations = _client_a_des_operations(client)

    if request.method == 'POST':
        if a_operations:
            messages.error(
                request,
                f"Impossible de supprimer {client.nom_complet} : ce client a un "
                f"historique d'opérations (séjours, ventes, factures...). "
                f"Désactivez-le au lieu de le supprimer."
            )
            return redirect('clients:detail', client_id=client.id)
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

    return render(request, 'clients/supprimer.html', {
        'client': client,
        'solde_total': solde_total,
        'a_operations': a_operations,
    })


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

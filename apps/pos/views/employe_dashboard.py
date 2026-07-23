from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.db.models import Q, Sum, Prefetch, Count
from django.utils import timezone
from ..models import SessionCaisse, SessionPlanning, Vente, LigneVente, ChangementCaissier, Commande, LigneCommande
from apps.rh.models import Pointage
from decimal import Decimal
from collections import defaultdict


def _build_timeline(employe, aujourdhui, limit=30):
    items = []

    # Ventes effectuées (PAYEE)
    for v in Vente.objects.filter(caissier=employe, statut='PAYEE').select_related('point_vente').order_by('-created_at')[:15]:
        items.append({
            'date': v.created_at,
            'type': 'vente',
            'icon': 'fa-cash-register',
            'color': 'text-green-400',
            'title': f"Vente {v.numero}",
            'subtitle': f"{v.montant_total:,.0f} F — {v.get_mode_paiement_display()}{' · ' + v.client_nom if v.client_nom else ''}",
            'point_vente': v.point_vente.nom if v.point_vente else '',
        })

    # Ventes encaissées (encaisse_par différent de caissier)
    for v in Vente.objects.filter(encaisse_par=employe).exclude(caissier=employe, statut='PAYEE').select_related('point_vente', 'caissier').order_by('-created_at')[:10]:
        items.append({
            'date': v.created_at,
            'type': 'encaissement',
            'icon': 'fa-hand-holding-usd',
            'color': 'text-blue-400',
            'title': f"Encaissement {v.numero}",
            'subtitle': f"{v.montant_total:,.0f} F — vente par {v.caissier.prenom if v.caissier else '?'}",
            'point_vente': v.point_vente.nom if v.point_vente else '',
        })

    # Annulations
    for v in Vente.objects.filter(caissier=employe, statut='ANNULEE').select_related('point_vente').order_by('-updated_at')[:10]:
        items.append({
            'date': v.updated_at,
            'type': 'annulation',
            'icon': 'fa-ban',
            'color': 'text-red-400',
            'title': f"Annulation {v.numero}",
            'subtitle': f"{v.montant_total:,.0f} F",
            'point_vente': v.point_vente.nom if v.point_vente else '',
        })

    # Commandes créées
    for c in Commande.objects.filter(created_by=employe).select_related('point_vente').annotate(nb_lignes=Count('lignes')).order_by('-date_commande')[:15]:
        items.append({
            'date': c.date_commande,
            'type': 'commande',
            'icon': 'fa-clipboard-list',
            'color': 'text-orange-400',
            'title': f"Commande {c.numero}",
            'subtitle': f"{c.get_statut_display()} · {c.nb_lignes} art.{' · ' + c.client_nom if c.client_nom else ''}",
            'point_vente': c.point_vente.nom if c.point_vente else '',
        })

    # Sessions ouvertes
    for s in SessionCaisse.objects.filter(caissier_ouverture=employe).select_related('point_vente').order_by('-date_ouverture')[:10]:
        items.append({
            'date': s.date_ouverture,
            'type': 'session_ouverte',
            'icon': 'fa-play-circle',
            'color': 'text-green-400',
            'title': f"Session #{s.id} ouverte",
            'subtitle': f"solde initial: {s.solde_initial:,.0f} F",
            'point_vente': s.point_vente.nom if s.point_vente else '',
        })

    # Sessions fermées
    for s in SessionCaisse.objects.filter(caissier_fermeture=employe, date_fermeture__isnull=False).select_related('point_vente').order_by('-date_fermeture')[:10]:
        items.append({
            'date': s.date_fermeture,
            'type': 'session_fermee',
            'icon': 'fa-stop-circle',
            'color': 'text-blue-400',
            'title': f"Session #{s.id} fermée",
            'subtitle': f"écart: {s.difference:+,.0f} F",
            'point_vente': s.point_vente.nom if s.point_vente else '',
        })

    # Changements de caissier
    for c in ChangementCaissier.objects.filter(
        Q(ancien_caissier=employe) | Q(nouveau_caissier=employe)
    ).select_related('ancien_caissier', 'nouveau_caissier', 'session__point_vente').order_by('-date_changement')[:10]:
        if c.ancien_caissier == employe:
            title = f"Relais donné — Session #{c.session_id}"
            subtitle = f"→ {c.nouveau_caissier.prenom} {c.nouveau_caissier.nom}{' (' + c.raison + ')' if c.raison else ''}"
        else:
            title = f"Relais pris — Session #{c.session_id}"
            subtitle = f"← {c.ancien_caissier.prenom} {c.ancien_caissier.nom}{' (' + c.raison + ')' if c.raison else ''}"
        items.append({
            'date': c.date_changement,
            'type': 'changement',
            'icon': 'fa-exchange-alt',
            'color': 'text-purple-400',
            'title': title,
            'subtitle': subtitle,
            'point_vente': c.session.point_vente.nom if c.session and c.session.point_vente else '',
        })

    # Pointages
    try:
        for p in Pointage.objects.filter(employe=employe).order_by('-date_pointage', '-heure_entree')[:10]:
            items.append({
                'date': timezone.make_aware(timezone.datetime.combine(p.date_pointage, p.heure_entree or timezone.datetime.min.time())) if p.heure_entree else timezone.now(),
                'type': 'pointage',
                'icon': 'fa-clock',
                'color': 'text-cyan-400',
                'title': f"Pointage {p.date_pointage.strftime('%d/%m/%Y')}",
                'subtitle': f"{p.heure_entree.strftime('%H:%M') if p.heure_entree else '--'} → {p.heure_sortie.strftime('%H:%M') if p.heure_sortie else '--'} ({p.heures_travaillees:.1f}h)",
                'point_vente': '',
            })
    except Exception:
        pass

    items.sort(key=lambda x: x['date'], reverse=True)
    return items[:limit]


@login_required
def employe_dashboard(request):
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employé trouvé.")
        return redirect('dashboard:index')

    from apps.pos.models import PointVente

    aujourdhui = timezone.localdate()
    now = timezone.localtime()

    # ─── Sessions ───
    sessions = SessionCaisse.objects.filter(
        Q(caissier_ouverture=employe) | Q(caissier_fermeture=employe)
    ).select_related('point_vente', 'caisse').order_by('-date_ouverture')[:30]

    session_ids = [s.id for s in sessions]
    ventes_par_session = {}
    if session_ids:
        ventes = Vente.objects.filter(
            session_caisse_id__in=session_ids, statut='PAYEE'
        ).select_related('caissier', 'table').prefetch_related(
            Prefetch('lignes', queryset=LigneVente.objects.select_related('produit', 'menu'))
        ).order_by('created_at')
        for v in ventes:
            ventes_par_session.setdefault(v.session_caisse_id, []).append(v)

    # ─── Plannings ───
    plannings = SessionPlanning.objects.filter(
        employe=employe
    ).exclude(statut='ANNULE').select_related('point_vente').order_by('-date', '-heure_debut')[:20]

    # ─── Stats du jour ───
    ventes_ajd = Vente.objects.filter(caissier=employe, created_at__date=aujourdhui)
    ventes_ajd_payee = ventes_ajd.filter(statut='PAYEE')
    ca_aujourdhui = ventes_ajd_payee.aggregate(total=Sum('montant_total'))['total'] or 0
    nb_ventes_aujourdhui = ventes_ajd_payee.count()
    nb_annulations_ajd = ventes_ajd.filter(statut='ANNULEE').count()

    commandes_ajd = Commande.objects.filter(created_by=employe, date_commande__date=aujourdhui)
    nb_commandes_ajd = commandes_ajd.count()
    nb_commandes_encours = commandes_ajd.exclude(statut__in=['SERVIE', 'LIVREE', 'ANNULEE']).count()

    mode_labels = dict(Vente.MODE_PAIEMENT_CHOICES)
    ventes_par_mode_ajd = {}
    for row in ventes_ajd_payee.values('mode_paiement').annotate(total=Sum('montant_total'), count=Count('id')):
        pm = row['mode_paiement']
        ventes_par_mode_ajd[pm] = {
            'total': row['total'], 'count': row['count'], 'label': mode_labels.get(pm, pm),
        }

    # ─── Journal de toutes les ventes (historique complet) ───
    toutes_ventes = Vente.objects.filter(
        caissier=employe
    ).select_related('point_vente', 'session_caisse', 'client', 'table').prefetch_related(
        Prefetch('lignes', queryset=LigneVente.objects.select_related('produit', 'menu'))
    ).order_by('-created_at')[:100]

    # ─── Dernières commandes ───
    dernieres_commandes = Commande.objects.filter(
        created_by=employe
    ).select_related('point_vente').annotate(
        nb_lignes=Count('lignes')
    ).order_by('-date_commande')[:20]

    # ─── Timeline ───
    timeline = _build_timeline(employe, aujourdhui)

    # ─── Accès POS ───
    user_groups = list(request.user.groups.values_list('name', flat=True))
    a_un_acces_pos = bool(employe.point_vente)
    pv_unique = employe.point_vente
    pv_ids = set(plannings.values_list('point_vente_id', flat=True))
    if pv_ids:
        a_un_acces_pos = True
        pvs = PointVente.objects.filter(id__in=pv_ids, actif=True)
        if pvs.count() == 1 and not pv_unique:
            pv_unique = pvs.first()
        elif pvs.count() > 1:
            pv_unique = None

    # ─── Annoter sessions ───
    for s in sessions:
        s.ventes_detail = ventes_par_session.get(s.id, [])
        s.total_ventes_calc = sum(v.montant_total for v in s.ventes_detail)
        s.nombre_ventes_calc = len(s.ventes_detail)
        pmt = defaultdict(lambda: {'count': 0, 'total': 0})
        for v in s.ventes_detail:
            pmt[v.mode_paiement]['count'] += 1
            pmt[v.mode_paiement]['total'] += float(v.montant_total)
        s.ventes_par_mode = {
            pm: {'count': d['count'], 'total': d['total'], 'label': mode_labels.get(pm, pm)}
            for pm, d in pmt.items()
        }

    context = {
        'employe': employe,
        'timeline': timeline,
        'sessions': sessions,
        'plannings': plannings,
        'toutes_ventes': toutes_ventes,
        'dernieres_commandes': dernieres_commandes,
        'ca_aujourdhui': ca_aujourdhui,
        'nb_ventes_aujourdhui': nb_ventes_aujourdhui,
        'nb_annulations_ajd': nb_annulations_ajd,
        'nb_commandes_ajd': nb_commandes_ajd,
        'nb_commandes_encours': nb_commandes_encours,
        'ventes_par_mode_ajd': ventes_par_mode_ajd,
        'nb_sessions': len(sessions),
        'nb_fermees': sum(1 for s in sessions if s.statut == 'FERMEE'),
        'nb_ouvertes': sum(1 for s in sessions if s.statut == 'OUVERTE'),
        'is_raf': 'RAF' in user_groups,
        'a_un_acces_pos': a_un_acces_pos,
        'pv_unique': pv_unique,
    }
    return render(request, 'pos/employe/dashboard.html', context)


@login_required
def employe_paiement_clients(request):
    """Espace dédié : paiement de dettes et dépôts clients pour les employés."""
    employe = getattr(request.user, 'employe', None)
    if not employe:
        messages.error(request, "Aucun profil employé trouvé.")
        return redirect('pos:employe_dashboard')

    from django.utils import timezone
    aujourdhui = timezone.localdate()
    planning = SessionPlanning.objects.filter(
        employe=employe, date=aujourdhui
    ).exclude(statut='ANNULE').select_related('point_vente__caisse').first()

    if not planning:
        messages.error(request, "Aucun planning aujourd'hui. Vous devez avoir un planning actif pour accéder à cet espace.")
        return redirect('pos:employe_dashboard')

    caisse = planning.point_vente.caisse if planning.point_vente else None
    if not caisse:
        messages.error(request, "Aucune caisse liée à votre point de vente.")
        return redirect('pos:employe_dashboard')

    return render(request, 'pos/employe/paiement_clients.html', {
        'caisse': caisse,
        'point_vente': planning.point_vente,
        'clients_employe': _get_clients_employe(employe),
    })


def _get_clients_employe(employe):
    """Retourne les clients ayant eu des transactions via le point de vente de l'employé."""
    from apps.paiements.models import Paiement
    from django.db.models import Sum, Q
    from ..models import SessionPlanning
    from django.utils import timezone

    aujourdhui = timezone.localdate()
    planning = SessionPlanning.objects.filter(
        employe=employe, date=aujourdhui
    ).exclude(statut='ANNULE').select_related('point_vente__caisse').first()
    if not planning or not planning.point_vente:
        return []

    # Chercher les paiements liés à ce point de vente (via la caisse)
    pv = planning.point_vente
    caisse = pv.caisse
    if not caisse:
        return []

    paiements = Paiement.objects.filter(
        caisse=caisse,
        client__isnull=False,
    ).exclude(
        client_id='C00000001'
    ).values('client_id', 'client__nom', 'client__telephone').annotate(
        total=Sum('montant'),
    ).order_by('-total')[:50]

    result = []
    for p in paiements:
        if not p['client_id']:
            continue
        credits = Paiement.objects.filter(
            caisse=caisse, client_id=p['client_id'],
            mode='CREDIT', statut='VALIDE',
        ).aggregate(total=Sum('montant'))['total'] or 0
        depots = Paiement.objects.filter(
            caisse=caisse, client_id=p['client_id'],
            mode__in=['ESPECES', 'CARTE', 'MOBILE_MONEY', 'CHEQUE'],
            statut='VALIDE', type_paiement='DEPOT',
        ).aggregate(total=Sum('montant'))['total'] or 0
        result.append({
            'id': p['client_id'],
            'nom': p['client__nom'] or 'Inconnu',
            'telephone': p['client__telephone'] or '',
            'total_credit': float(credits),
            'total_depots': float(depots),
            'solde': float(credits - depots),
        })
    return result


@login_required
@require_http_methods(["POST"])
def api_paiement_clients_processer(request):
    """API : payer une dette ou faire un dépôt client (espace employé)."""
    import json
    from apps.paiements.services.paiement_engine import PaiementEngine
    from apps.clients.models import Client
    from django.utils import timezone
    try:
        data = json.loads(request.body)
        client_id = data.get('client_id')
        montant = data.get('montant')
        mode = data.get('mode', 'ESPECES')
        operation_type = data.get('type', 'dette')

        if not all([client_id, montant]):
            return JsonResponse({'success': False, 'error': 'Champs obligatoires manquants'})
        if float(montant) <= 0:
            return JsonResponse({'success': False, 'error': 'Montant doit être > 0'})

        client = Client.objects.filter(id=client_id).first()
        if not client:
            return JsonResponse({'success': False, 'error': 'Client introuvable'})

        # Vérifier le planning et auto-sélectionner la caisse
        employe = getattr(request.user, 'employe', None)
        if not employe:
            return JsonResponse({'success': False, 'error': 'Employé introuvable'})

        aujourdhui = timezone.localdate()
        planning = SessionPlanning.objects.filter(
            employe=employe, date=aujourdhui
        ).exclude(statut='ANNULE').select_related('point_vente__caisse').first()

        if not planning:
            return JsonResponse({'success': False, 'error': 'Aucun planning actif aujourd\'hui'})

        caisse = planning.point_vente.caisse if planning.point_vente else None
        if not caisse:
            return JsonResponse({'success': False, 'error': 'Aucune caisse liée à votre point de vente'})

        paiement = PaiementEngine.encaisser({
            'client_id': client_id,
            'montant': montant,
            'mode': mode,
            'caisse_id': caisse.id,
            'type_paiement': 'DEPOT',
            'notes': f"{'Paiement dette' if operation_type == 'dette' else 'Dépôt'} - {client.nom_complet}",
        }, request.user)

        return JsonResponse({
            'success': True,
            'message': f'{"Paiement" if operation_type == "dette" else "Dépôt"} de {montant} F enregistré',
            'paiement': {'id': paiement.id, 'reference': paiement.reference},
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return JsonResponse({'success': False, 'error': str(e)})

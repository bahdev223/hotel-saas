from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from collections import defaultdict

from ..models import SessionCaisse, SessionPlanning, Vente, Commande, PointVente
from apps.rh.models import Pointage


@login_required
def api_mon_espace(request):
    """API 360° : toutes les données du dashboard employé en une requête"""
    employe = getattr(request.user, 'employe', None)
    if not employe:
        return JsonResponse({'success': False, 'error': 'Profil employé non trouvé'})

    aujourdhui = timezone.localdate()
    now = timezone.localtime()

    # ─── Infos employé ───
    info = {
        'nom': employe.nom, 'prenom': employe.prenom,
        'nom_complet': employe.nom_complet,
        'matricule': employe.matricule or '',
        'poste': employe.poste.nom if employe.poste else '',
        'departement': employe.departement.nom if hasattr(employe, 'departement') and employe.departement else '',
        'date_embauche': employe.date_embauche.strftime('%d/%m/%Y') if employe.date_embauche else '',
        'actif': employe.actif,
        'salaire_base': float(employe.salaire_base) if hasattr(employe, 'salaire_base') and employe.salaire_base else None,
    }

    # ─── Stats du jour ───
    ventes_ajd = Vente.objects.filter(caissier=employe, created_at__date=aujourdhui)
    ventes_ajd_payee = ventes_ajd.filter(statut='PAYEE')
    ca_aujourdhui = float(ventes_ajd_payee.aggregate(t=Sum('montant_total'))['t'] or 0)
    nb_ventes_aujourdhui = ventes_ajd_payee.count()
    nb_annulations_ajd = ventes_ajd.filter(statut='ANNULEE').count()
    commandes_ajd = Commande.objects.filter(created_by=employe, date_commande__date=aujourdhui)
    nb_commandes_ajd = commandes_ajd.count()
    nb_commandes_encours = commandes_ajd.exclude(statut__in=['SERVIE', 'LIVREE', 'ANNULEE']).count()

    # ─── Ventes par mode ───
    mode_labels = dict(Vente.MODE_PAIEMENT_CHOICES)
    ventes_par_mode_ajd = {}
    for row in ventes_ajd_payee.values('mode_paiement').annotate(total=Sum('montant_total'), count=Count('id')):
        pm = row['mode_paiement']
        ventes_par_mode_ajd[pm] = {
            'total': float(row['total']), 'count': row['count'],
            'label': mode_labels.get(pm, pm),
        }

    # ─── Sessions ───
    sessions = SessionCaisse.objects.filter(
        Q(caissier_ouverture=employe) | Q(caissier_fermeture=employe)
    ).select_related('point_vente', 'caisse').order_by('-date_ouverture')[:20]

    sessions_data = []
    for s in sessions:
        sessions_data.append({
            'id': s.id, 'statut': s.statut,
            'date_ouverture': s.date_ouverture.strftime('%d/%m %H:%M'),
            'point_vente': s.point_vente.nom if s.point_vente else '',
            'total_ventes': float(s.total_ventes),
            'nombre_ventes': s.nombre_ventes,
            'solde_initial': float(s.solde_initial),
            'fermee_par_raf': s.ferme_par_raf_id is not None,
            'fonds_collectes': s.fonds_collectes,
        })

    # ─── Plannings ───
    plannings_qs = SessionPlanning.objects.filter(
        employe=employe
    ).exclude(statut='ANNULE').select_related('point_vente').order_by('-date', '-heure_debut')[:30]

    plannings_data = []
    planning_aujourdhui = []
    for p in plannings_qs:
        pd = {
            'id': p.id, 'date': p.date.strftime('%d/%m'),
            'debut': p.heure_debut.strftime('%H:%M'),
            'fin': p.heure_fin.strftime('%H:%M'),
            'point_vente': p.point_vente.nom if p.point_vente else '',
            'point_vente_code': p.point_vente.code if p.point_vente else '',
            'statut': p.statut,
        }
        plannings_data.append(pd)
        if p.date == aujourdhui:
            planning_aujourdhui.append(pd)

    # ─── Accès POS ───
    pv_ids = set()
    if employe.point_vente_id:
        pv_ids.add(employe.point_vente_id)
    for pid in SessionPlanning.objects.filter(employe=employe, date=aujourdhui).exclude(
        statut='ANNULE'
    ).values_list('point_vente_id', flat=True):
        pv_ids.add(pid)
    pvs = PointVente.objects.filter(id__in=pv_ids, actif=True)
    pv_access = []
    for pv in pvs:
        session = SessionCaisse.objects.filter(caisse=pv.caisse, statut='OUVERTE').first()
        pv_access.append({
            'id': pv.id, 'code': pv.code, 'nom': pv.nom,
            'session_active': session.caissier_ouverture.nom_complet if session and session.caissier_ouverture else None,
        })

    # ─── Timeline (dernières 15 activités) ───
    timeline = []
    for v in Vente.objects.filter(caissier=employe, statut='PAYEE').select_related('point_vente').order_by('-created_at')[:8]:
        timeline.append({
            'date': v.created_at.strftime('%d/%m %H:%M'), 'type': 'vente',
            'icon': 'fa-cash-register', 'color': '#4ade80',
            'text': f"Vente {v.numero} — {float(v.montant_total):,.0f} F",
            'detail': v.get_mode_paiement_display(),
            'pv': v.point_vente.nom if v.point_vente else '',
        })
    for c in Commande.objects.filter(created_by=employe).select_related('point_vente').order_by('-date_commande')[:8]:
        timeline.append({
            'date': c.date_commande.strftime('%d/%m %H:%M'), 'type': 'commande',
            'icon': 'fa-clipboard-list', 'color': '#fb923c',
            'text': f"Commande {c.numero} — {c.get_statut_display()}",
            'pv': c.point_vente.nom if c.point_vente else '',
        })
    timeline.sort(key=lambda x: x['date'], reverse=True)
    timeline = timeline[:15]

    return JsonResponse({
        'success': True,
        'info': info,
        'stats': {
            'ca_aujourdhui': ca_aujourdhui,
            'nb_ventes_aujourdhui': nb_ventes_aujourdhui,
            'nb_annulations_ajd': nb_annulations_ajd,
            'nb_commandes_ajd': nb_commandes_ajd,
            'nb_commandes_encours': nb_commandes_encours,
            'nb_sessions': len(sessions),
            'nb_ouvertes': sum(1 for s in sessions_data if s['statut'] == 'OUVERTE'),
            'nb_fermees': sum(1 for s in sessions_data if s['statut'] == 'FERMEE'),
        },
        'ventes_par_mode': ventes_par_mode_ajd,
        'sessions': sessions_data,
        'plannings': plannings_data,
        'planning_aujourdhui': planning_aujourdhui,
        'pv_access': pv_access,
        'timeline': timeline,
    })

from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.db.models import Sum, Count, Q
from django.utils import timezone
from collections import defaultdict

from ..models import SessionCaisse, Vente, Commande, PointVente, ShiftEmploye, AffectationPointVente, CaissePointVente


@login_required
def api_mon_espace(request):
    employe = getattr(request.user, 'employe', None)
    if not employe:
        return JsonResponse({'success': False, 'error': 'Profil employ\u00e9 non trouv\u00e9'})

    aujourdhui = timezone.localdate()

    info = {
        'nom': employe.nom, 'prenom': employe.prenom,
        'nom_complet': employe.nom_complet, 'matricule': employe.matricule or '',
        'poste': employe.poste.nom if employe.poste else '',
        'departement': employe.departement.nom if hasattr(employe, 'departement') and employe.departement else '',
        'date_embauche': employe.date_embauche.strftime('%d/%m/%Y') if employe.date_embauche else '',
        'actif': employe.actif,
        'salaire_base': float(employe.salaire_base) if hasattr(employe, 'salaire_base') and employe.salaire_base else None,
    }

    ventes_ajd = Vente.objects.filter(caissier=employe, created_at__date=aujourdhui)
    ventes_ajd_payee = ventes_ajd.filter(statut='PAYEE')
    ca_aujourdhui = float(ventes_ajd_payee.aggregate(t=Sum('montant_total'))['t'] or 0)
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
            'total': float(row['total']), 'count': row['count'],
            'label': mode_labels.get(pm, pm),
        }

    sessions = SessionCaisse.objects.filter(
        Q(ouverte_par=employe) | Q(fermee_par=employe)
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
            'validee': s.statut == 'VALIDEE',
        })

    affectations = AffectationPointVente.objects.filter(employe=employe, actif=True).values_list('point_vente_id', flat=True)
    shifts = ShiftEmploye.objects.filter(
        affectation__employe=employe,
    ).exclude(statut='ANNULE').select_related('affectation__point_vente').order_by('-debut_prevu')[:30]

    plannings_data = []
    planning_aujourdhui = []
    for s in shifts:
        pv = s.affectation.point_vente if s.affectation else None
        pd = {
            'id': s.id, 'date': s.debut_prevu.strftime('%d/%m'),
            'debut': s.debut_prevu.strftime('%H:%M'),
            'fin': s.fin_prevue.strftime('%H:%M'),
            'point_vente': pv.nom if pv else '',
            'point_vente_code': pv.code if pv else '',
            'statut': s.statut,
        }
        plannings_data.append(pd)
        if s.debut_prevu.date() == aujourdhui:
            planning_aujourdhui.append(pd)

    pv_ids = set(affectations)
    pvs = PointVente.objects.filter(id__in=pv_ids, actif=True)
    pv_access = []
    for pv in pvs:
        cpv = CaissePointVente.objects.filter(point_vente=pv, actif=True).select_related('caisse').first()
        caisse = cpv.caisse if cpv else None
        session = SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').first() if caisse else None
        pv_access.append({
            'id': pv.id, 'code': pv.code, 'nom': pv.nom,
            'session_active': session.ouverte_par.nom_complet if session and session.ouverte_par else None,
        })

    timeline = []
    for v in Vente.objects.filter(caissier=employe, statut='PAYEE').select_related('point_vente').order_by('-created_at')[:8]:
        timeline.append({
            'date': v.created_at.strftime('%d/%m %H:%M'), 'type': 'vente',
            'icon': 'fa-cash-register', 'color': '#4ade80',
            'text': f"Vente {v.numero} \u2014 {float(v.montant_total):,.0f} F",
            'detail': v.get_mode_paiement_display(), 'pv': v.point_vente.nom if v.point_vente else '',
        })
    for c in Commande.objects.filter(created_by=employe).select_related('point_vente').order_by('-date_commande')[:8]:
        timeline.append({
            'date': c.date_commande.strftime('%d/%m %H:%M'), 'type': 'commande',
            'icon': 'fa-clipboard-list', 'color': '#fb923c',
            'text': f"Commande {c.numero} \u2014 {c.get_statut_display()}",
            'pv': c.point_vente.nom if c.point_vente else '',
        })
    timeline.sort(key=lambda x: x['date'], reverse=True)
    timeline = timeline[:15]

    return JsonResponse({
        'success': True, 'info': info,
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
        'ventes_par_mode': ventes_par_mode_ajd, 'sessions': sessions_data,
        'plannings': plannings_data, 'planning_aujourdhui': planning_aujourdhui,
        'pv_access': pv_access, 'timeline': timeline,
    })

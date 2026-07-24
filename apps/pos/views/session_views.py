from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied
from django.db.models import Prefetch, Q
import json
from decimal import Decimal

from ..models import PointVente, SessionCaisse, LigneVente, AffectationPointVente, CaissePointVente
from ..services.caisse_session_service import CaisseSessionService, get_session_autorisee, get_session_active_caisse
from apps.rh.models import Employe
from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF
from apps.tresorerie.models import Caisse


def _user_can_gerer_sessions(user):
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists()


def _get_employe_pv_ids(employe):
    if not employe:
        return []
    return list(AffectationPointVente.objects.filter(employe=employe, actif=True).values_list('point_vente_id', flat=True))


def _get_planning_actif(employe, point_vente):
    """Retourne le ShiftEmploye actif, ou None."""
    if not employe or not point_vente:
        return None
    from django.utils import timezone
    from ..models import ShiftEmploye
    now = timezone.localtime()
    affectation = AffectationPointVente.objects.filter(
        employe=employe, point_vente=point_vente, actif=True,
    ).first()
    if not affectation:
        return None
    return ShiftEmploye.objects.filter(
        affectation=affectation,
        debut_prevu__lte=now,
        fin_prevue__gte=now,
        statut__in=('PLANIFIE', 'CONFIRME', 'EN_COURS'),
    ).first()


@login_required
def sessions_liste(request):
    from django.utils import timezone
    employe = getattr(request.user, 'employe', None)
    est_admin = request.user.is_superuser or _user_can_gerer_sessions(request.user)

    sessions = SessionCaisse.objects.all()
    if not est_admin:
        pv_ids = _get_employe_pv_ids(employe)
        sessions = sessions.filter(point_vente_id__in=pv_ids) if pv_ids else sessions.none()
    sessions = sessions.order_by('-date_ouverture')

    point_vente_id = request.GET.get('point_vente')
    if point_vente_id:
        sessions = sessions.filter(point_vente_id=point_vente_id)
    statut = request.GET.get('statut')
    if statut:
        sessions = sessions.filter(statut=statut)

    aujourdhui = timezone.localdate()
    sessions_aujourdhui = sessions.filter(date_ouverture__date=aujourdhui).count()
    sessions_ouvertes = sessions.filter(statut='OUVERTE').count()
    ca_total = sum(s.total_ventes for s in sessions if s.total_ventes)

    pv_ids = _get_employe_pv_ids(employe)
    context = {
        'sessions': sessions[:100],
        'points_vente': PointVente.objects.filter(actif=True) if est_admin else PointVente.objects.filter(id__in=pv_ids) if pv_ids else PointVente.objects.none(),
        'sessions_aujourdhui': sessions_aujourdhui,
        'sessions_ouvertes': sessions_ouvertes,
        'ca_total': ca_total,
    }
    return render(request, 'pos/sessions/liste.html', context)


@login_required
def session_detail(request, session_id):
    session = get_session_autorisee(session_id, request.user)
    from ..models import Vente
    ventes = session.ventes.all().order_by('-created_at')

    employe_id = request.GET.get('employe_id')
    if employe_id:
        ventes = ventes.filter(caissier_id=employe_id)
    produit_nom = request.GET.get('produit_nom')
    if produit_nom:
        ventes = ventes.filter(
            Q(lignes__produit__nom=produit_nom) | Q(lignes__menu__nom=produit_nom)
        ).distinct()

    if session.date_ouverture:
        ventes_sans_session = Vente.objects.filter(
            session_caisse__isnull=True,
            point_vente=session.point_vente,
            created_at__gte=session.date_ouverture,
        )
        if session.date_fermeture:
            ventes_sans_session = ventes_sans_session.filter(created_at__lte=session.date_fermeture)
        if employe_id:
            ventes_sans_session = ventes_sans_session.filter(caissier_id=employe_id)
        if produit_nom:
            ventes_sans_session = ventes_sans_session.filter(
                Q(lignes__produit__nom=produit_nom) | Q(lignes__menu__nom=produit_nom)
            ).distinct()
        ventes = (ventes | ventes_sans_session).order_by('-created_at')

    ventes = ventes.prefetch_related(Prefetch('lignes', queryset=LigneVente.objects.select_related('produit', 'menu')))
    ventes_list = list(ventes)

    stats_paiement = {}
    for mode in ('ESPECES', 'CARTE', 'MOBILE_MONEY', 'COMPTE_CLIENT'):
        stats_paiement[mode] = sum(
            v.montant_total for v in ventes_list if v.mode_paiement == mode and v.statut == 'PAYEE'
        )

    top_produits = CaisseSessionService.get_session_top_produits(session, limit=10)
    produit_list = CaisseSessionService.get_session_produit_list(session)

    employes_ids = set(v.caissier_id for v in ventes_list if v.caissier_id)
    employes_session = list(Employe.objects.filter(id__in=employes_ids).values_list('id', 'nom', 'prenom'))

    context = {
        'session': session, 'ventes': ventes_list,
        'stats_paiement': stats_paiement, 'top_produits': top_produits,
        'produit_list': produit_list, 'employe_id': employe_id,
        'employes_session': employes_session,
    }
    return render(request, 'pos/sessions/detail.html', context)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_ouverture_session(request):
    try:
        data = json.loads(request.body)
        caisse_id = data.get('caisse_id')
        point_vente_id = data.get('point_vente_id')
        caissier_id = data.get('caissier_id')

        caisse = get_object_or_404(Caisse, id=caisse_id)
        point_vente = get_object_or_404(PointVente, id=point_vente_id)
        caissier = get_object_or_404(Employe, id=caissier_id)

        if not _user_can_gerer_sessions(request.user):
            employe = getattr(request.user, 'employe', None)
            if not employe:
                return JsonResponse({'success': False, 'error': 'Non autoris\u00e9 sur ce point de vente'}, status=403)
            pv_ids = _get_employe_pv_ids(employe)
            a_acces = point_vente.id in pv_ids or _get_planning_actif(employe, point_vente) is not None
            if not a_acces:
                return JsonResponse({'success': False, 'error': 'Non autoris\u00e9 sur ce point de vente'}, status=403)

        shift = _get_planning_actif(caissier, point_vente)
        if not shift:
            return JsonResponse({
                'success': False, 'error_code': 'PLANNING_REQUIS',
                'error': f"{caissier.nom_complet} n'a aucun shift actif sur {point_vente.nom}."
            }, status=403)

        session = CaisseSessionService.ouverture_session(
            caisse=caisse, point_vente=point_vente, caissier=caissier, shift=shift,
        )

        return JsonResponse({
            'success': True, 'session_id': session.id,
            'solde_initial': float(session.solde_initial),
            'message': f"Session ouverte avec {caissier.nom} {caissier.prenom} (solde: {session.solde_initial:,.0f} F)"
        })

    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_fermeture_session(request):
    if not _user_can_gerer_sessions(request.user):
        return JsonResponse({'success': False, 'error': 'Seuls la comptabilit\u00e9 et la direction peuvent fermer les sessions.'}, status=403)
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        especes_comptees = Decimal(str(data.get('especes_comptees', 0)))
        fermee_par_id = data.get('fermee_par_id')
        notes = data.get('notes', '')
        depot = data.get('depot')

        session = get_session_autorisee(session_id, request.user, require_open=True)
        if fermee_par_id:
            fermee_par = get_object_or_404(Employe, id=fermee_par_id)
        else:
            fermee_par = session.ouverte_par

        resultat = CaisseSessionService.fermeture_session(
            session=session, especes_comptees=especes_comptees,
            fermee_par=fermee_par, notes=notes, depot=depot,
        )

        message = f"Session ferm\u00e9e. \u00c9cart: {resultat['ecart']} F"
        if abs(resultat['ecart']) > 5000:
            message += " (Attention: \u00e9cart important)"

        return JsonResponse({
            'success': True, 'message': message,
            'ecart': float(resultat['ecart']),
            'total_ventes': float(resultat['total_ventes']),
        })

    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_cloturer_et_rouvrir(request):
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        employe = getattr(request.user, 'employe', None)
        if not employe:
            return JsonResponse({'success': False, 'error': 'Aucun profil employ\u00e9'}, status=400)

        session = get_session_autorisee(session_id, request.user, require_open=True)
        if not session.point_vente:
            return JsonResponse({'success': False, 'error': 'Session sans point de vente'}, status=400)

        CaisseSessionService.annuler_session(session)

        reponse = {
            'success': True,
            'session_fermee': {'id': session.id},
            'nouvelle_session': None,
        }

        nouveau_shift = _get_planning_actif(employe, session.point_vente)
        if nouveau_shift:
            ns = CaisseSessionService.ouverture_session(
                caisse=session.caisse, point_vente=session.point_vente,
                caissier=employe, shift=nouveau_shift,
            )
            reponse['nouvelle_session'] = {
                'id': ns.id, 'solde_initial': float(ns.solde_initial),
                'date_ouverture': ns.date_ouverture.strftime('%d/%m/%Y %H:%M'),
            }

        return JsonResponse(reponse)

    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_session_active(request, point_vente_id):
    point_vente = get_object_or_404(PointVente, id=point_vente_id)

    if not _user_can_gerer_sessions(request.user):
        employe = getattr(request.user, 'employe', None)
        pv_ids = _get_employe_pv_ids(employe)
        a_acces = employe and (point_vente.id in pv_ids or _get_planning_actif(employe, point_vente) is not None)
        if not a_acces:
            return JsonResponse({'success': False, 'error': 'Non autoris\u00e9'}, status=403)

    cpv = CaissePointVente.objects.filter(point_vente=point_vente, actif=True).select_related('caisse').first()
    if not cpv:
        return JsonResponse({'success': False, 'error': 'Aucune caisse associ\u00e9e'})

    session = get_session_active_caisse(cpv.caisse)

    if session:
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'caissier': {
                    'id': session.ouverte_par.id,
                    'nom': session.ouverte_par.nom,
                    'prenom': session.ouverte_par.prenom,
                    'nom_complet': session.ouverte_par.nom_complet,
                } if session.ouverte_par else None,
                'solde_initial': float(session.solde_initial),
                'date_ouverture': session.date_ouverture.strftime('%d/%m/%Y %H:%M'),
                'total_ventes': float(session.total_ventes),
                'nombre_ventes': session.nombre_ventes,
            }
        })

    return JsonResponse({'success': False, 'session': None})


@login_required
def api_verifier_etat_pos(request, point_vente_id):
    point_vente = get_object_or_404(PointVente, id=point_vente_id, actif=True)
    employe = getattr(request.user, 'employe', None)

    cpv = CaissePointVente.objects.filter(point_vente=point_vente, actif=True).select_related('caisse').first()
    if not employe or not cpv:
        return JsonResponse({'success': False, 'error': 'Employ\u00e9 ou caisse non trouv\u00e9'})
    caisse = cpv.caisse

    if not _user_can_gerer_sessions(request.user):
        pv_ids = _get_employe_pv_ids(employe)
        a_acces = point_vente.id in pv_ids or _get_planning_actif(employe, point_vente) is not None
        if not a_acces:
            return JsonResponse({'success': False, 'error': 'Non autoris\u00e9 sur ce point de vente'}, status=403)

    session_active = get_session_active_caisse(caisse)
    planning_actif = _get_planning_actif(employe, point_vente)

    return JsonResponse({
        'success': True,
        'session_active': session_active.id if session_active else None,
        'planning_expire': False,
        'session_a_fermer': None,
        'nouveau_planning': {
            'debut': planning_actif.debut_prevu.strftime('%H:%M'),
            'fin': planning_actif.fin_prevue.strftime('%H:%M'),
            'solde_initial': float(caisse.solde),
            'point_vente': point_vente.nom,
        } if planning_actif and not session_active else None,
        'planning_actif': {
            'debut': planning_actif.debut_prevu.strftime('%H:%M'),
            'fin': planning_actif.fin_prevue.strftime('%H:%M'),
        } if planning_actif else None,
    })


@login_required
def api_caissiers_disponibles(request, point_vente_id):
    point_vente = get_object_or_404(PointVente, id=point_vente_id)

    if not _user_can_gerer_sessions(request.user):
        employe = getattr(request.user, 'employe', None)
        pv_ids = _get_employe_pv_ids(employe)
        a_acces = employe and (point_vente.id in pv_ids or _get_planning_actif(employe, point_vente) is not None)
        if not a_acces:
            return JsonResponse({'success': False, 'error': 'Non autoris\u00e9'}, status=403)

    affectations = AffectationPointVente.objects.filter(
        point_vente=point_vente, actif=True
    ).filter(
        Q(peut_ouvrir_caisse=True) | Q(peut_encaisser=True)
    ).select_related('employe')

    return JsonResponse({
        'success': True,
        'caissiers': [
            {
                'id': a.employe.id, 'nom': a.employe.nom, 'prenom': a.employe.prenom,
                'nom_complet': a.employe.nom_complet, 'matricule': a.employe.matricule,
                'role': a.get_role_display(),
            }
            for a in affectations
        ]
    })


import csv
from django.http import HttpResponse


@login_required
def session_export_csv(request, session_id):
    if not _user_can_gerer_sessions(request.user):
        messages.error(request, "Seuls la comptabilit\u00e9 et la direction peuvent exporter les sessions.")
        return redirect('dashboard:index')
    session = get_object_or_404(SessionCaisse, id=session_id)
    ventes = session.ventes.filter(statut='PAYEE').order_by('created_at')

    response = HttpResponse(content_type='text/csv; charset=utf-8-sig')
    response['Content-Disposition'] = f'attachment; filename="session_{session.id}_{session.date_ouverture.strftime("%Y%m%d")}.csv"'

    writer = csv.writer(response)
    writer.writerow(['Ticket', 'Date', 'Mode paiement', 'Montant', 'Caissier'])
    for v in ventes:
        writer.writerow([
            v.numero,
            v.created_at.strftime('%d/%m/%Y %H:%M'),
            v.get_mode_paiement_display(),
            f'{v.montant_total:,.0f} F',
            v.caissier.nom_complet if v.caissier else '',
        ])
    writer.writerow([])
    writer.writerow(['Total ventes', '', '', f'{session.total_ventes:,.0f} F', ''])
    writer.writerow(['Nombre ventes', '', '', session.nombre_ventes, ''])
    writer.writerow(['Solde initial', '', '', f'{session.solde_initial:,.0f} F', ''])
    writer.writerow(['Caissier', '', '', session.ouverte_par.nom_complet if session.ouverte_par else '', ''])
    if session.date_fermeture:
        writer.writerow(['Ferm\u00e9 par', '', '', session.fermee_par.nom_complet if session.fermee_par else '', ''])
    return response

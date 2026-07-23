# apps/pos/views/session_views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.exceptions import PermissionDenied
import json
from decimal import Decimal

from ..models import PointVente, SessionCaisse, ChangementCaissier, LigneVente
from ..services.caisse_session_service import CaisseSessionService, get_planning_actif, get_session_autorisee
from ..constants import POINT_VENTE_GROUP_MAPPING
from apps.rh.models import Employe
from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF
from django.db.models import Prefetch, Q


def _user_can_gerer_sessions(user):
    """Seuls PATRON/MANAGER/COMPTABLE/RAF ou superuser peuvent gérer les sessions"""
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists()


@login_required
def sessions_liste(request):
    """Liste des sessions de caisse — filtrée par rôle et point de vente"""
    from django.utils import timezone
    employe = getattr(request.user, 'employe', None)
    est_admin = request.user.is_superuser or _user_can_gerer_sessions(request.user)

    sessions = SessionCaisse.objects.all()
    if not est_admin:
        sessions = sessions.filter(point_vente_id=employe.point_vente_id) if employe and employe.point_vente_id else sessions.none()
    sessions = sessions.order_by('-date_ouverture')

    point_vente_id = request.GET.get('point_vente')
    if point_vente_id:
        sessions = sessions.filter(point_vente_id=point_vente_id)

    statut = request.GET.get('statut')
    if statut:
        sessions = sessions.filter(statut=statut)

    # Stats pour les tuiles
    aujourdhui = timezone.localdate()
    sessions_aujourdhui = sessions.filter(date_ouverture__date=aujourdhui).count()
    sessions_ouvertes = sessions.filter(statut='OUVERTE').count()
    ca_total = sum(s.total_ventes for s in sessions if s.total_ventes)

    context = {
        'sessions': sessions[:100],
        'points_vente': PointVente.objects.filter(actif=True) if est_admin else PointVente.objects.filter(id=employe.point_vente_id) if employe and employe.point_vente_id else PointVente.objects.none(),
        'sessions_aujourdhui': sessions_aujourdhui,
        'sessions_ouvertes': sessions_ouvertes,
        'ca_total': ca_total,
    }
    return render(request, 'pos/sessions/liste.html', context)


@login_required
def session_detail(request, session_id):
    """Détail d'une session — accessible au caissier de son propre PV, admin voit tout"""
    session = get_session_autorisee(session_id, request.user)
    from ..models import Vente
    changements = session.changements.all().order_by('-date_changement')

    # Ventes de la session
    ventes = session.ventes.all().order_by('-created_at')

    employe_id = request.GET.get('employe_id')
    if employe_id:
        ventes = ventes.filter(caissier_id=employe_id)

    # Filtre par produit
    produit_nom = request.GET.get('produit_nom')
    if produit_nom:
        ventes = ventes.filter(
            Q(lignes__produit__nom=produit_nom) | Q(lignes__menu__nom=produit_nom)
        ).distinct()

    # Fallback: ventes orphelines
    if session.date_ouverture:
        ventes_sans_session = Vente.objects.filter(
            session_caisse__isnull=True,
            point_vente=session.point_vente,
            created_at__gte=session.date_ouverture,
        )
        if session.date_fermeture:
            ventes_sans_session = ventes_sans_session.filter(
                created_at__lte=session.date_fermeture
            )
        if employe_id:
            ventes_sans_session = ventes_sans_session.filter(caissier_id=employe_id)
        if produit_nom:
            ventes_sans_session = ventes_sans_session.filter(
                Q(lignes__produit__nom=produit_nom) | Q(lignes__menu__nom=produit_nom)
            ).distinct()
        ventes = (ventes | ventes_sans_session).order_by('-created_at')

    ventes = ventes.prefetch_related(Prefetch('lignes', queryset=LigneVente.objects.select_related('produit', 'menu')))
    ventes_list = list(ventes)

    # Stats par mode de paiement
    stats_paiement = {}
    for mode in ('ESPECES', 'CARTE', 'MOBILE_MONEY', 'COMPTE_CLIENT'):
        stats_paiement[mode] = sum(
            v.montant_total for v in ventes_list
            if v.mode_paiement == mode and v.statut == 'PAYEE'
        )

    # Top produits
    top_produits = CaisseSessionService.get_session_top_produits(session, limit=10)

    # Liste des produits pour le filtre
    produit_list = CaisseSessionService.get_session_produit_list(session)

    employes_ids = set(v.caissier_id for v in ventes_list if v.caissier_id)
    employes_qs = Employe.objects.filter(id__in=employes_ids).values_list('id', 'nom', 'prenom')
    employes_session = list(employes_qs)

    context = {
        'session': session,
        'changements': changements,
        'ventes': ventes_list,
        'stats_paiement': stats_paiement,
        'top_produits': top_produits,
        'produit_list': produit_list,
        'employe_id': employe_id,
        'employes_session': employes_session,
    }
    return render(request, 'pos/sessions/detail.html', context)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_ouverture_session(request):
    """API pour ouvrir une session de caisse"""
    try:
        data = json.loads(request.body)
        
        caisse_id = data.get('caisse_id')
        point_vente_id = data.get('point_vente_id')
        caissier_id = data.get('caissier_id')

        from apps.tresorerie.models import Caisse
        caisse = get_object_or_404(Caisse, id=caisse_id)
        point_vente = get_object_or_404(PointVente, id=point_vente_id)
        caissier = get_object_or_404(Employe, id=caissier_id)

        # Vérifier l'accès au point de vente : PV maison OU planning actif sur ce PV
        # (même règle que a_acces_pos() — un employé sans PV maison mais avec un
        # planning ponctuel ailleurs doit pouvoir ouvrir sa session)
        if not _user_can_gerer_sessions(request.user):
            employe = getattr(request.user, 'employe', None)
            if not employe:
                return JsonResponse({'success': False, 'error': 'Non autorisé sur ce point de vente'}, status=403)
            a_acces = employe.point_vente_id == point_vente.id or get_planning_actif(employe, point_vente) is not None
            if not a_acces:
                return JsonResponse({'success': False, 'error': 'Non autorisé sur ce point de vente'}, status=403)

        # Verrou : ouverture de session uniquement avec un planning actif
        planning = get_planning_actif(caissier, point_vente)
        if not planning:
            return JsonResponse({
                'success': False,
                'error_code': 'PLANNING_REQUIS',
                'error': f"{caissier.nom_complet} n'a aucun planning actif sur {point_vente.nom}. Créez d'abord un planning."
            }, status=403)

        session = CaisseSessionService.ouverture_session(
            caisse=caisse,
            point_vente=point_vente,
            caissier=caissier,
            debut_prevu=planning.heure_debut,
            fin_prevu=planning.heure_fin,
            planning=planning,
        )
        
        return JsonResponse({
            'success': True,
            'session_id': session.id,
            'solde_initial': float(session.solde_initial),
            'message': f'Session ouverte avec {caissier.nom} {caissier.prenom} (solde: {session.solde_initial:,.0f} F)'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
    
    




@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_fermeture_session(request):
    """API pour fermer une session de caisse"""
    if not _user_can_gerer_sessions(request.user):
        return JsonResponse({'success': False, 'error': 'Seuls la comptabilité et la direction peuvent fermer les sessions.'}, status=403)
    try:
        data = json.loads(request.body)
        
        session_id = data.get('session_id')
        solde_reel = Decimal(str(data.get('solde_reel', 0)))
        caissier_fermeture_id = data.get('caissier_fermeture_id')
        notes = data.get('notes', '')
        depot = data.get('depot')
        if depot is not None:
            depot = Decimal(str(depot))
        
        session = get_session_autorisee(session_id, request.user, require_open=True)
        if caissier_fermeture_id:
            caissier = get_object_or_404(Employe, id=caissier_fermeture_id)
        else:
            caissier = session.caissier_ouverture
        
        resultat = CaisseSessionService.fermeture_session(
            session=session,
            solde_reel=solde_reel,
            caissier_fermeture=caissier,
            notes=notes,
            depot=depot
        )
        
        message = f"Session fermée. Écart: {resultat['difference']} F"
        if abs(resultat['difference']) > 5000:
            message += " (Attention: écart important)"
        
        return JsonResponse({
            'success': True,
            'message': message,
            'difference': float(resultat['difference']),
            'solde_attendu': float(resultat['solde_attendu']),
            'solde_reel': float(resultat['solde_reel']),
            'depot': float(resultat['depot']) if resultat.get('depot') else 0,
            'solde_restant': float(resultat['solde_restant']) if resultat.get('solde_restant') else 0,
            'total_ventes': float(resultat['total_ventes'])
        })
        
    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)    
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_cloturer_et_rouvrir(request):
    """Ferme la session courante (fin de planning) et ouvre la suivante si planning actif."""
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        employe = getattr(request.user, 'employe', None)
        if not employe:
            return JsonResponse({'success': False, 'error': 'Aucun profil employé'}, status=400)

        session = get_session_autorisee(session_id, request.user, require_open=True)
        if not session.point_vente:
            return JsonResponse({'success': False, 'error': 'Session sans point de vente'}, status=400)

        resultat = CaisseSessionService.fermer_et_preparer_prochaine(
            session=session,
            caissier=employe,
            point_vente=session.point_vente,
        )

        reponse = {
            'success': True,
            'session_fermee': {
                'id': resultat['session_fermee'].id,
                'solde_attendu': float(resultat['session_fermee'].solde_attendu),
                'solde_reel': float(resultat['session_fermee'].solde_reel),
            },
            'nouvelle_session': None,
        }
        if resultat['nouvelle_session']:
            ns = resultat['nouvelle_session']
            reponse['nouvelle_session'] = {
                'id': ns.id,
                'solde_initial': float(ns.solde_initial),
                'date_ouverture': ns.date_ouverture.strftime('%d/%m/%Y %H:%M'),
            }

        return JsonResponse(reponse)

    except PermissionDenied as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=403)
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})


@login_required
def api_session_active(request, point_vente_id):
    """Récupère la session active pour un point de vente"""
    point_vente = get_object_or_404(PointVente, id=point_vente_id)

    # Vérifier l'accès au point de vente : PV maison OU planning actif sur ce PV
    if not _user_can_gerer_sessions(request.user):
        employe = getattr(request.user, 'employe', None)
        a_acces = employe and (employe.point_vente_id == point_vente.id or get_planning_actif(employe, point_vente) is not None)
        if not a_acces:
            return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    session = CaisseSessionService.get_session_active(point_vente.caisse_id)
    
    if session:
        return JsonResponse({
            'success': True,
            'session': {
                'id': session.id,
                'caissier': {
                    'id': session.caissier_ouverture.id,
                    'nom': session.caissier_ouverture.nom,
                    'prenom': session.caissier_ouverture.prenom,
                    'nom_complet': session.caissier_ouverture.nom_complet
                } if session.caissier_ouverture else None,
                'solde_initial': float(session.solde_initial),
                'date_ouverture': session.date_ouverture.strftime('%d/%m/%Y %H:%M'),
                'total_ventes': float(session.total_ventes),
                'nombre_ventes': session.nombre_ventes
            }
        })
    
    return JsonResponse({'success': False, 'session': None})


@login_required
def api_verifier_etat_pos(request, point_vente_id):
    """Polling endpoint : vérifie l'état session + planning pour le POS (lecture seule, ne ferme rien)"""
    point_vente = get_object_or_404(PointVente, id=point_vente_id, actif=True)
    employe = getattr(request.user, 'employe', None)
    caisse = point_vente.caisse

    if not employe or not caisse:
        return JsonResponse({'success': False, 'error': 'Employé ou caisse non trouvé'})

    # L'employé doit appartenir à ce point de vente (PV maison) OU y avoir un planning actif
    if not _user_can_gerer_sessions(request.user):
        a_acces = employe.point_vente_id == point_vente.id or get_planning_actif(employe, point_vente) is not None
        if not a_acces:
            return JsonResponse({'success': False, 'error': 'Non autorisé sur ce point de vente'}, status=403)

    etat = CaisseSessionService.verifier_session_planning(
        caisse=caisse, employe=employe, point_vente=point_vente,
    )

    session_active = etat.get('session_active')
    planning_expire = etat.get('planning_expire', False)

    return JsonResponse({
        'success': True,
        'session_active': session_active.id if session_active else None,
        'planning_expire': planning_expire,
        'session_a_fermer': etat.get('session_a_fermer'),
        'nouveau_planning': {
            'debut': etat['nouveau_planning']['debut'],
            'fin': etat['nouveau_planning']['fin'],
            'solde_initial': etat['nouveau_planning']['solde_initial'],
            'point_vente': etat['nouveau_planning']['point_vente'],
        } if etat.get('nouveau_planning') else None,
        'planning_actif': {
            'debut': etat['planning_actif'].heure_debut.strftime('%H:%M'),
            'fin': etat['planning_actif'].heure_fin.strftime('%H:%M'),
        } if etat.get('planning_actif') else None,
    })





@login_required
def api_caissiers_disponibles(request, point_vente_id):
    """API pour récupérer les caissiers disponibles pour un point de vente"""
    point_vente = get_object_or_404(PointVente, id=point_vente_id)

    # Vérifier l'accès au point de vente : PV maison OU planning actif sur ce PV
    if not _user_can_gerer_sessions(request.user):
        employe = getattr(request.user, 'employe', None)
        a_acces = employe and (employe.point_vente_id == point_vente.id or get_planning_actif(employe, point_vente) is not None)
        if not a_acces:
            return JsonResponse({'success': False, 'error': 'Non autorisé'}, status=403)

    # Récupérer les employés qui ont le bon groupe pour ce point de vente
    from django.contrib.auth.models import Group
    
    required_group = POINT_VENTE_GROUP_MAPPING.get(point_vente.emplacement, 'CAISSIER')
    
    try:
        group = Group.objects.get(name=required_group)
        employes = Employe.objects.filter(
            actif=True,
            user__groups=group
        ).select_related('poste', 'user')
    except Group.DoesNotExist:
        employes = Employe.objects.filter(actif=True).select_related('poste', 'user')
    
    return JsonResponse({
        'success': True,
        'caissiers': [
            {
                'id': e.id,
                'nom': e.nom,
                'prenom': e.prenom,
                'nom_complet': e.nom_complet,
                'matricule': e.matricule,
                'poste': e.poste.intitule if e.poste else None
            }
            for e in employes
        ]
    })
    


import csv
from django.http import HttpResponse


@login_required
def session_export_csv(request, session_id):
    """Export CSV des ventes d'une session"""
    if not _user_can_gerer_sessions(request.user):
        messages.error(request, "Seuls la comptabilité et la direction peuvent exporter les sessions.")
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
    writer.writerow(['Solde attendu', '', '', f'{session.solde_attendu:,.0f} F', ''])
    writer.writerow(['Solde réel', '', '', f'{session.solde_reel:,.0f} F' if session.solde_reel else '', ''])
    writer.writerow(['Dépôt', '', '', f'{session.depot:,.0f} F' if session.depot else '0', ''])
    writer.writerow(['Écart', '', '', f'{session.difference:,.0f} F', ''])
    
    return response
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
from ..services.caisse_session_service import (
    CaisseSessionService,
    get_session_autorisee,
    get_session_active_caisse,
    get_session_non_finalisee_caisse,
)
from ..services.access_service import POSAccessService
from ..constants import ActionPOS, ModeAccesPOS, POINTS_VENTE_OPERATIONNELS
from apps.rh.models import Employe
from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF
from apps.tresorerie.models import Caisse


def _user_can_gerer_sessions(user):
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists()


def _get_employe_pv_ids(employe):
    if not employe or not getattr(employe, "user", None):
        return []
    return list(
        POSAccessService.points_accessibles(user=employe.user)
        .values_list("id", flat=True)
    )


def _get_planning_actif(employe, point_vente):
    if not employe or not point_vente:
        return None
    decision = POSAccessService.check(
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.ACCEDER,
    )
    if not decision.allowed or not decision.shift_id:
        return None
    from ..models import ShiftEmploye
    return ShiftEmploye.objects.filter(pk=decision.shift_id).first()


@login_required
def sessions_liste(request):
    from django.utils import timezone
    employe = getattr(request.user, 'employe', None)
    est_admin = request.user.is_superuser or _user_can_gerer_sessions(request.user)

    sessions = SessionCaisse.objects.filter(point_vente__type__in=POINTS_VENTE_OPERATIONNELS)
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
        'points_vente': (
            PointVente.objects.filter(actif=True, type__in=POINTS_VENTE_OPERATIONNELS)
            if est_admin
            else PointVente.objects.filter(id__in=pv_ids, type__in=POINTS_VENTE_OPERATIONNELS)
            if pv_ids
            else PointVente.objects.none()
        ),
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
    for mode in ('ESPECES', 'CARTE', 'MOBILE_MONEY', 'CHEQUE', 'COMPTE_CLIENT'):
        stats_paiement[mode] = sum(
            v.montant_total for v in ventes_list if v.mode_paiement == mode and v.statut == 'PAYEE'
        )

    top_produits = CaisseSessionService.get_session_top_produits(session, limit=10)
    produit_list = CaisseSessionService.get_session_produit_list(session)

    employes_ids = set(v.caissier_id for v in ventes_list if v.caissier_id)
    employes_session = list(Employe.objects.filter(id__in=employes_ids).values_list('id', 'nom', 'prenom'))

    comptage = getattr(session, 'comptage', None)
    especes_attendues = (
        comptage.especes_attendues
        if comptage
        else Decimal(str(session.solde_initial or 0))
        + Decimal(str(session.total_especes or 0))
    )
    context = {
        'session': session,
        'ventes': ventes_list,
        'stats_paiement': stats_paiement,
        'top_produits': top_produits,
        'produit_list': produit_list,
        'employe_id': employe_id,
        'employes_session': employes_session,
        'comptage': comptage,
        'especes_attendues': especes_attendues,
        'can_manage_sessions': _user_can_gerer_sessions(request.user),
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
        point_vente = get_object_or_404(
            PointVente,
            id=point_vente_id,
            actif=True,
            type__in=POINTS_VENTE_OPERATIONNELS,
        )
        caissier = get_object_or_404(Employe, id=caissier_id, actif=True)

        if not CaissePointVente.objects.filter(
            point_vente=point_vente,
            caisse=caisse,
            actif=True,
        ).exists():
            return JsonResponse({
                'success': False,
                'error_code': 'CAISSE_POINT_VENTE_INVALIDE',
                'error': "Cette caisse n'est pas rattachée à ce point de vente.",
            }, status=400)

        demandeur = getattr(request.user, 'employe', None)
        if not _user_can_gerer_sessions(request.user):
            if not demandeur or demandeur.id != caissier.id:
                return JsonResponse({
                    'success': False,
                    'error_code': 'OUVERTURE_POUR_AUTRUI_INTERDITE',
                    'error': "Un employé ne peut ouvrir que sa propre session.",
                }, status=403)

        decision = POSAccessService.check(
            user=caissier.user,
            employe=caissier,
            point_vente=point_vente,
            action=ActionPOS.OUVRIR_CAISSE,
        )
        if not decision.allowed:
            return JsonResponse({
                'success': False,
                'error_code': decision.reason,
                'error': f"Ouverture de caisse refusée pour {caissier.nom_complet} ({decision.reason}).",
            }, status=403)

        shift = None
        if decision.mode == ModeAccesPOS.PLANNING:
            from ..models import ShiftEmploye
            shift = ShiftEmploye.objects.filter(pk=decision.shift_id).first()
            if shift is None:
                return JsonResponse({
                    'success': False,
                    'error_code': 'PLANNING_REQUIS',
                    'error': f"{caissier.nom_complet} n'a aucun shift actif sur {point_vente.nom}.",
                }, status=403)

        session = CaisseSessionService.ouverture_session(
            caisse=caisse,
            point_vente=point_vente,
            caissier=caissier,
            shift=shift,
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
    try:
        data = json.loads(request.body)
        session_id = data.get('session_id')
        especes_comptees = Decimal(str(data.get('especes_comptees', 0)))
        fermee_par_id = data.get('fermee_par_id')
        notes = data.get('notes', '')
        depot = data.get('depot')
        montant_carte = data.get('montant_carte')
        montant_mobile = data.get('montant_mobile')
        montant_cheque = data.get('montant_cheque')

        session = get_session_autorisee(
            session_id,
            request.user,
            require_open=True,
            allow_owner_finalize=True,
        )
        demandeur = getattr(request.user, "employe", None)
        est_supervision = _user_can_gerer_sessions(request.user)

        if not est_supervision:
            autorise, raison = CaisseSessionService.autoriser_finalisation_session(
                session,
                demandeur,
            )
            if not autorise:
                return JsonResponse({
                    "success": False,
                    "error_code": raison,
                    "error": f"Fermeture de caisse refusée ({raison}).",
                }, status=403)
            fermee_par = demandeur
        elif demandeur is not None:
            # Le superviseur est lui-même l'acteur de la clôture : on ne permet
            # pas de signer arbitrairement l'opération au nom d'un autre employé.
            fermee_par = demandeur
        elif fermee_par_id:
            # Fallback réservé aux comptes techniques superuser sans profil RH.
            fermee_par = get_object_or_404(Employe, id=fermee_par_id, actif=True)
        else:
            fermee_par = session.ouverte_par

        resultat = CaisseSessionService.fermeture_session(
            session=session,
            especes_comptees=especes_comptees,
            fermee_par=fermee_par,
            notes=notes,
            depot=depot,
            montant_carte=montant_carte,
            montant_mobile=montant_mobile,
            montant_cheque=montant_cheque,
        )

        message = f"Session ferm\u00e9e. \u00c9cart: {resultat['ecart']} F"
        if abs(resultat['ecart']) > 5000:
            message += " (Attention: \u00e9cart important)"

        return JsonResponse({
            'success': True,
            'message': message,
            'ecart': float(resultat['ecart']),
            'ecart_especes': float(resultat['ecart_especes']),
            'ecart_carte': float(resultat['ecart_carte']),
            'ecart_mobile': float(resultat['ecart_mobile']),
            'ecart_cheque': float(resultat['ecart_cheque']),
            'especes_attendues': float(resultat['especes_attendues']),
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
    return JsonResponse({
        'success': False,
        'error_code': 'FLOW_SESSION_V2',
        'error': (
            "La clôture automatique sans comptage est désactivée. "
            "Effectuez le comptage, fermez la session, puis ouvrez la suivante."
        ),
    }, status=409)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_demarrer_passation(request):
    try:
        data = json.loads(request.body or "{}")
        session = get_session_autorisee(
            data.get("session_id"),
            request.user,
            require_open=True,
            allow_owner_finalize=True,
        )
        demandeur = getattr(request.user, "employe", None)
        if not _user_can_gerer_sessions(request.user):
            if not demandeur or session.ouverte_par_id != demandeur.id:
                return JsonResponse({
                    "success": False,
                    "error_code": "SESSION_APPARTIENT_A_UN_AUTRE_CAISSIER",
                    "error": "Seul le caissier propriétaire peut démarrer la passation.",
                }, status=403)
        session = CaisseSessionService.demarrer_passation(
            session,
            motif=data.get("motif", "Passation manuelle"),
            par=demandeur,
        )
        return JsonResponse({
            "success": True,
            "session": {
                "id": session.id,
                "statut": session.statut,
                "date_passation": session.date_passation.isoformat() if session.date_passation else None,
                "passation_jusqua": session.passation_jusqua.isoformat() if session.passation_jusqua else None,
                "motif": session.motif_passation,
            },
        })
    except PermissionDenied as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=403)
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def api_valider_session(request):
    if not _user_can_gerer_sessions(request.user):
        return JsonResponse({
            "success": False,
            "error": "Validation réservée à la direction, comptabilité ou RAF.",
        }, status=403)
    try:
        data = json.loads(request.body or "{}")
        session = get_object_or_404(
            SessionCaisse,
            id=data.get("session_id"),
            point_vente__type__in=POINTS_VENTE_OPERATIONNELS,
        )
        validateur = getattr(request.user, "employe", None)
        if (
            validateur is None
            and request.user.is_superuser
            and data.get("validee_par_id")
        ):
            # Seul un compte technique superuser sans profil RH peut fournir
            # explicitement l'acteur métier de validation.
            validateur = get_object_or_404(
                Employe,
                id=data.get("validee_par_id"),
                actif=True,
            )
        if validateur is None:
            return JsonResponse({
                "success": False,
                "error": "Un profil employé validateur est obligatoire.",
            }, status=400)
        session = CaisseSessionService.valider_session(session, validateur)
        return JsonResponse({
            "success": True,
            "session_id": session.id,
            "statut": session.statut,
            "date_validation": session.date_validation.isoformat(),
            "validee_par": validateur.nom_complet,
        })
    except Exception as exc:
        return JsonResponse({"success": False, "error": str(exc)}, status=400)


@login_required
def api_session_active(request, point_vente_id):
    point_vente = get_object_or_404(
        PointVente,
        id=point_vente_id,
        actif=True,
        type__in=POINTS_VENTE_OPERATIONNELS,
    )
    cpv = (
        CaissePointVente.objects
        .filter(point_vente=point_vente, actif=True)
        .select_related('caisse')
        .order_by('-principale', 'id')
        .first()
    )
    if not cpv:
        return JsonResponse({'success': False, 'error': 'Aucune caisse associée'})

    session = get_session_non_finalisee_caisse(cpv.caisse)

    if not _user_can_gerer_sessions(request.user):
        decision = POSAccessService.check(
            user=request.user,
            point_vente=point_vente,
            action=ActionPOS.ACCEDER,
        )
        if not decision.allowed:
            employe = getattr(request.user, "employe", None)
            owner_finalize = False
            if (
                session
                and employe
                and session.ouverte_par_id == employe.id
            ):
                owner_finalize, _ = (
                    CaisseSessionService.autoriser_finalisation_session(
                        session,
                        employe,
                    )
                )
            if not owner_finalize:
                return JsonResponse({
                    'success': False,
                    'error_code': decision.reason,
                    'error': f"Accès refusé ({decision.reason}).",
                }, status=403)

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
                'statut': session.statut,
                'mode_acces_ouverture': session.mode_acces_ouverture,
                'raison_acces_ouverture': session.raison_acces_ouverture,
                'acces_expire_le': session.acces_expire_le.isoformat() if session.acces_expire_le else None,
                'date_passation': session.date_passation.isoformat() if session.date_passation else None,
                'passation_jusqua': session.passation_jusqua.isoformat() if session.passation_jusqua else None,
                'total_ventes': float(session.total_ventes),
                'nombre_ventes': session.nombre_ventes,
                'proprietaire': (
                    getattr(request.user, 'employe', None) is not None
                    and session.ouverte_par_id == request.user.employe.id
                ),
            }
        })

    return JsonResponse({'success': False, 'session': None})


@login_required
def api_verifier_etat_pos(request, point_vente_id):
    point_vente = get_object_or_404(
        PointVente,
        id=point_vente_id,
        actif=True,
        type__in=POINTS_VENTE_OPERATIONNELS,
    )
    employe = getattr(request.user, 'employe', None)

    cpv = (
        CaissePointVente.objects
        .filter(point_vente=point_vente, actif=True)
        .select_related('caisse')
        .order_by("-principale", "id")
        .first()
    )
    if not employe or not cpv:
        return JsonResponse({
            'success': False,
            'error': 'Employé ou caisse non trouvé',
        }, status=400)
    caisse = cpv.caisse

    # Décision du demandeur : sert à savoir s'il peut utiliser le POS maintenant.
    decision = POSAccessService.check(
        user=request.user,
        employe=employe,
        point_vente=point_vente,
        action=ActionPOS.ACCEDER,
    )

    session_non_finalisee = get_session_non_finalisee_caisse(caisse)

    # La transition financière dépend du propriétaire de la session, jamais du
    # simple visiteur qui interroge cet endpoint.
    owner_decision = None
    if session_non_finalisee and session_non_finalisee.ouverte_par:
        owner = session_non_finalisee.ouverte_par
        if owner.user_id:
            owner_decision = POSAccessService.check(
                user=owner.user,
                employe=owner,
                point_vente=point_vente,
                action=ActionPOS.ENCAISSER,
            )

    if (
        session_non_finalisee
        and session_non_finalisee.statut == 'OUVERTE'
        and owner_decision is not None
        and not owner_decision.allowed
    ):
        session_non_finalisee = CaisseSessionService.demarrer_passation(
            session_non_finalisee,
            motif=f"Droit d'encaisser expiré: {owner_decision.reason}",
        )

    if (
        session_non_finalisee
        and session_non_finalisee.statut == 'EN_PASSATION'
        and session_non_finalisee.passation_jusqua
        and timezone.now() > session_non_finalisee.passation_jusqua
    ):
        session_non_finalisee.statut = 'EN_COMPTAGE'
        session_non_finalisee.save(update_fields=['statut', 'updated_at'])

    est_proprietaire = bool(
        session_non_finalisee
        and session_non_finalisee.ouverte_par_id == employe.id
    )
    peut_finaliser = False
    if est_proprietaire:
        peut_finaliser, _ = CaisseSessionService.autoriser_finalisation_session(
            session_non_finalisee,
            employe,
        )

    if (
        not decision.allowed
        and not _user_can_gerer_sessions(request.user)
        and not (est_proprietaire and peut_finaliser)
    ):
        return JsonResponse({
            'success': False,
            'error_code': decision.reason,
            'error': f"Accès refusé ({decision.reason}).",
            'acces': decision.to_dict(),
        }, status=403)

    session_active = (
        session_non_finalisee
        if session_non_finalisee and session_non_finalisee.statut == 'OUVERTE'
        else None
    )
    session_a_fermer = (
        session_non_finalisee
        if session_non_finalisee
        and session_non_finalisee.statut in ('EN_PASSATION', 'EN_COMPTAGE')
        and est_proprietaire
        and peut_finaliser
        else None
    )

    from ..models import ShiftEmploye
    planning_actif = (
        ShiftEmploye.objects.filter(pk=decision.shift_id).first()
        if decision.allowed and decision.shift_id else None
    )

    raison_session = (
        owner_decision.reason
        if owner_decision is not None
        else decision.reason
    )

    return JsonResponse({
        'success': True,
        'session_active': session_active.id if session_active else None,
        'planning_expire': bool(session_a_fermer),
        'session_a_fermer': {
            'id': session_a_fermer.id,
            'statut': session_a_fermer.statut,
            'point_vente': point_vente.nom,
            'raison': raison_session,
            'solde_initial': float(session_a_fermer.solde_initial),
            'total_ventes': float(session_a_fermer.total_ventes),
            'total_especes': float(session_a_fermer.total_especes),
            'especes_attendues': float(
                Decimal(str(session_a_fermer.solde_initial or 0))
                + Decimal(str(session_a_fermer.total_especes or 0))
            ),
            'total_carte': float(session_a_fermer.total_carte),
            'total_mobile_money': float(session_a_fermer.total_mobile_money),
            'total_cheque': float(session_a_fermer.total_cheque),
            'date_passation': (
                session_a_fermer.date_passation.isoformat()
                if session_a_fermer.date_passation else None
            ),
            'passation_jusqua': (
                session_a_fermer.passation_jusqua.isoformat()
                if session_a_fermer.passation_jusqua else None
            ),
        } if session_a_fermer else None,
        'nouveau_planning': {
            'date': timezone.localdate().strftime('%d/%m/%Y'),
            'debut': planning_actif.debut_prevu.strftime('%H:%M'),
            'fin': planning_actif.fin_prevue.strftime('%H:%M'),
            'solde_initial': float(caisse.solde),
            'point_vente': point_vente.nom,
        } if planning_actif and not session_non_finalisee else None,
        'planning_actif': {
            'debut': planning_actif.debut_prevu.strftime('%H:%M'),
            'fin': planning_actif.fin_prevue.strftime('%H:%M'),
        } if planning_actif else None,
        'acces': decision.to_dict(),
        'session_owner_access': (
            owner_decision.to_dict()
            if owner_decision is not None else None
        ),
    })


@login_required
def api_caissiers_disponibles(request, point_vente_id):
    point_vente = get_object_or_404(
        PointVente,
        id=point_vente_id,
        actif=True,
        type__in=POINTS_VENTE_OPERATIONNELS,
    )

    if not _user_can_gerer_sessions(request.user):
        demandeur = POSAccessService.check(
            user=request.user,
            point_vente=point_vente,
            action=ActionPOS.ACCEDER,
        )
        if not demandeur.allowed:
            return JsonResponse({
                'success': False,
                'error_code': demandeur.reason,
                'error': f"Accès refusé ({demandeur.reason}).",
            }, status=403)

    employes = Employe.objects.filter(
        actif=True,
        user__isnull=False,
    ).select_related("user", "poste").order_by("nom", "prenom")

    caissiers = []
    for employe in employes:
        decision = POSAccessService.check(
            user=employe.user,
            employe=employe,
            point_vente=point_vente,
            action=ActionPOS.OUVRIR_CAISSE,
        )
        if not decision.allowed:
            continue
        caissiers.append({
            'id': employe.id,
            'nom': employe.nom,
            'prenom': employe.prenom,
            'nom_complet': employe.nom_complet,
            'matricule': employe.matricule,
            'mode_acces': decision.mode,
            'access_reason': decision.reason,
            'expires_at': (
                decision.expires_at.isoformat()
                if decision.expires_at else None
            ),
        })

    return JsonResponse({'success': True, 'caissiers': caissiers})


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

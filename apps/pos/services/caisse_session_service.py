from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q
from decimal import Decimal
from datetime import timedelta

from apps.pos.models import SessionCaisse, Vente, ComptageSession, CaissePointVente, AffectationPointVente
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse


def get_session_autorisee(session_id, user, require_open=False, allow_owner_finalize=False):
    from django.core.exceptions import PermissionDenied
    from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF
    from apps.pos.constants import ActionPOS, POINTS_VENTE_OPERATIONNELS
    from apps.pos.services.access_service import POSAccessService

    session = (
        SessionCaisse.objects
        .filter(id=session_id, point_vente__type__in=POINTS_VENTE_OPERATIONNELS)
        .select_related("point_vente", "ouverte_par")
        .first()
    )
    if session is None:
        raise PermissionDenied("Session introuvable ou hors périmètre Bar/Restaurant.")

    est_supervision = (
        user.is_superuser
        or user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists()
    )
    if not est_supervision:
        decision = POSAccessService.check(
            user=user,
            point_vente=session.point_vente,
            action=ActionPOS.ACCEDER,
        )
        if not decision.allowed:
            employe = getattr(user, "employe", None)
            owner_can_finalize = False
            if (
                allow_owner_finalize
                and employe is not None
                and session.ouverte_par_id == employe.id
            ):
                owner_can_finalize, _ = (
                    CaisseSessionService.autoriser_finalisation_session(
                        session,
                        employe,
                    )
                )

            if not owner_can_finalize:
                raise PermissionDenied(
                    f"Session non autorisée pour ce profil ({decision.reason})."
                )

    if require_open and session.statut not in ("OUVERTE", "EN_PASSATION", "EN_COMPTAGE"):
        raise PermissionDenied("Cette session n'est plus ouverte.")
    return session


def get_session_active_caisse(caisse):
    if not caisse:
        return None
    return SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').first()


def get_session_non_finalisee_caisse(caisse):
    if not caisse:
        return None
    return SessionCaisse.objects.filter(
        caisse=caisse,
        statut__in=("OUVERTE", "EN_PASSATION", "EN_COMPTAGE"),
    ).order_by("-date_ouverture").first()


def get_session_active_pv(point_vente):
    """Session OUVERTE uniquement (nouvelle activité / nouvel encaissement)."""
    if not point_vente:
        return None
    cpv = CaissePointVente.objects.filter(point_vente=point_vente, actif=True).select_related('caisse').first()
    if not cpv:
        return None
    return get_session_active_caisse(cpv.caisse)


def get_session_encaissement_caisse(caisse):
    """Session pouvant encore solder de l'existant : OUVERTE ou PASSATION."""
    if not caisse:
        return None
    return SessionCaisse.objects.filter(
        caisse=caisse,
        statut__in=("OUVERTE", "EN_PASSATION"),
    ).order_by("-date_ouverture").first()


class CaisseSessionService:

    ECART_JUSTIFICATION_SEUIL = Decimal("5000")

    @staticmethod
    @transaction.atomic
    def ouverture_session(caisse, point_vente, caissier, shift=None):
        from apps.pos.constants import ActionPOS, ModeAccesPOS, POINTS_VENTE_OPERATIONNELS
        from apps.pos.services.access_service import POSAccessService

        if (
            not point_vente
            or not point_vente.actif
            or point_vente.type not in POINTS_VENTE_OPERATIONNELS
        ):
            raise ValueError("La caisse POS est limitée aux points Bar/Restaurant actifs.")
        if not caissier or not caissier.actif or not caissier.user_id:
            raise ValueError("Le caissier doit être un employé actif avec un compte utilisateur.")

        if not CaissePointVente.objects.filter(
            point_vente=point_vente,
            caisse=caisse,
            actif=True,
        ).exists():
            raise ValueError("Cette caisse n'est pas rattachée à ce point de vente.")

        decision = POSAccessService.check(
            user=caissier.user,
            employe=caissier,
            point_vente=point_vente,
            action=ActionPOS.OUVRIR_CAISSE,
        )
        if not decision.allowed:
            raise ValueError(
                f"Ouverture de caisse non autorisée ({decision.reason})."
            )
        if decision.mode == ModeAccesPOS.PLANNING:
            if shift is None or shift.id != decision.shift_id:
                raise ValueError(
                    "Le shift actif autorisant cette ouverture doit être fourni."
                )

        caisse_verrouillee = Caisse.objects.select_for_update().get(pk=caisse.pk)
        session_active = SessionCaisse.objects.select_for_update().filter(
            caisse=caisse_verrouillee,
            statut__in=['OUVERTE', 'EN_PASSATION', 'EN_COMPTAGE'],
        ).first()

        if session_active:
            raise ValueError(
                "La caisse poss\u00e8de d\u00e9j\u00e0 une session non finalis\u00e9e. "
                "Finalisez la session précédente avant d'en ouvrir une nouvelle."
            )

        permissions_snapshot = {}
        if decision.affectation_id:
            affectation = AffectationPointVente.objects.filter(
                pk=decision.affectation_id,
            ).first()
            if affectation:
                permissions_snapshot = {
                    "role": affectation.role,
                    "peut_vendre": affectation.peut_vendre,
                    "peut_encaisser": affectation.peut_encaisser,
                    "peut_ouvrir_caisse": affectation.peut_ouvrir_caisse,
                    "peut_fermer_caisse": affectation.peut_fermer_caisse,
                    "peut_annuler_vente": affectation.peut_annuler_vente,
                    "peut_accorder_remise": affectation.peut_accorder_remise,
                    "peut_consulter_rapports": affectation.peut_consulter_rapports,
                }
        else:
            permissions_snapshot = {
                "scope": "DIRECTION_TOTAL",
                "peut_vendre": True,
                "peut_encaisser": True,
                "peut_ouvrir_caisse": True,
                "peut_fermer_caisse": True,
                "peut_annuler_vente": True,
                "peut_accorder_remise": True,
                "peut_consulter_rapports": True,
            }

        session = SessionCaisse.objects.create(
            caisse=caisse_verrouillee,
            point_vente=point_vente,
            ouverte_par=caissier,
            solde_initial=caisse_verrouillee.solde,
            shift=shift,
            statut='OUVERTE',
            mode_acces_ouverture=decision.mode or "",
            raison_acces_ouverture=decision.reason,
            affectation_ouverture_id=decision.affectation_id,
            shift_ouverture_id=decision.shift_id,
            acces_expire_le=decision.expires_at,
            permissions_ouverture=permissions_snapshot,
        )
        return session

    @staticmethod
    def autoriser_finalisation_session(session, employe):
        """Autorise uniquement le propriétaire financier selon le snapshot d'ouverture."""
        if not session or not employe or session.ouverte_par_id != employe.id:
            return False, "SESSION_APPARTIENT_A_UN_AUTRE_CAISSIER"
        if not employe.actif:
            return False, "EMPLOYE_INACTIF"
        snapshot = session.permissions_ouverture or {}
        if "peut_fermer_caisse" in snapshot:
            if bool(snapshot.get("peut_fermer_caisse")):
                return True, "SNAPSHOT_FERMETURE_AUTORISEE"
            return False, "PERMISSION_FERMETURE_ABSENTE_A_OUVERTURE"

        # Compatibilité : sessions déjà ouvertes avant Session Caisse V2.
        from apps.pos.constants import ActionPOS
        from apps.pos.services.access_service import POSAccessService
        decision = POSAccessService.check_capability(
            user=employe.user,
            employe=employe,
            point_vente=session.point_vente,
            action=ActionPOS.FERMER_CAISSE,
        )
        return decision.allowed, (
            "LEGACY_CAPACITE_FERMETURE"
            if decision.allowed else decision.reason
        )

    @staticmethod
    @transaction.atomic
    def demarrer_passation(session, motif="", moment=None):
        session = (
            SessionCaisse.objects.select_for_update()
            .select_related("point_vente")
            .get(pk=session.pk)
        )
        if session.statut == "EN_PASSATION":
            return session
        if session.statut != "OUVERTE":
            raise ValueError("Seule une session ouverte peut passer en passation.")

        now = moment or timezone.now()
        delai = int(getattr(session.point_vente, "delai_passation_minutes", 15) or 0)
        session.statut = "EN_PASSATION"
        session.date_passation = now
        session.passation_jusqua = now + timedelta(minutes=max(0, delai))
        session.motif_passation = (motif or "Fin de créneau / passation")[:255]
        session.save(update_fields=[
            "statut",
            "date_passation",
            "passation_jusqua",
            "motif_passation",
            "updated_at",
        ])
        return session

    @staticmethod
    def autoriser_encaissement_session(session, encaisseur, commande=None, moment=None):
        """Protège la responsabilité financière d'une session.

        Une session appartient à son ouvreur. En PASSATION, il peut uniquement
        terminer un encaissement concernant une commande créée avant la
        passation, pendant la fenêtre de grâce.
        """
        from apps.pos.constants import ActionPOS
        from apps.pos.services.access_service import POSAccessService

        now = moment or timezone.now()
        if not session or not encaisseur or session.ouverte_par_id != encaisseur.id:
            return False, "SESSION_APPARTIENT_A_UN_AUTRE_CAISSIER"

        if session.statut == "OUVERTE":
            decision = POSAccessService.check(
                user=encaisseur.user,
                employe=encaisseur,
                point_vente=session.point_vente,
                action=ActionPOS.ENCAISSER,
                moment=now,
            )
            return decision.allowed, decision.reason

        if session.statut == "EN_PASSATION":
            if session.passation_jusqua and now > session.passation_jusqua:
                return False, "PASSATION_EXPIREE"
            if (
                commande is not None
                and session.date_passation
                and commande.date_commande > session.date_passation
            ):
                return False, "COMMANDE_APRES_PASSATION"

            if not encaisseur.actif:
                return False, "EMPLOYE_INACTIF"

            snapshot = session.permissions_ouverture or {}
            if "peut_encaisser" in snapshot:
                if not bool(snapshot.get("peut_encaisser")):
                    return False, "PERMISSION_ENCAISSEMENT_ABSENTE_A_OUVERTURE"
                return True, "PASSATION_GRACE_ACTIVE"

            # Compatibilité : session créée avant l'introduction du snapshot.
            decision = POSAccessService.check_capability(
                user=encaisseur.user,
                employe=encaisseur,
                point_vente=session.point_vente,
                action=ActionPOS.ENCAISSER,
                moment=now,
            )
            return decision.allowed, (
                "PASSATION_GRACE_LEGACY"
                if decision.allowed else decision.reason
            )

        return False, "SESSION_NON_ENCAISSABLE"

    @staticmethod
    @transaction.atomic
    def fermeture_session(session, especes_comptees, fermee_par, notes='',
                          montant_carte=None, montant_mobile=None, montant_cheque=None,
                          depot=None):
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        if session.statut not in ('OUVERTE', 'EN_PASSATION', 'EN_COMPTAGE'):
            raise ValueError("La session n'est pas ouverte, en passation ou en comptage")

        ventes = Vente.objects.filter(session_caisse=session, statut='PAYEE')
        total_especes = ventes.filter(
            mode_paiement='ESPECES'
        ).aggregate(total=Sum('montant_total'))['total'] or Decimal('0')
        total_carte = ventes.filter(
            mode_paiement__in=['CARTE', 'VISA', 'MASTERCARD']
        ).aggregate(total=Sum('montant_total'))['total'] or Decimal('0')
        total_mobile = ventes.filter(
            mode_paiement='MOBILE_MONEY'
        ).aggregate(total=Sum('montant_total'))['total'] or Decimal('0')
        total_cheque = ventes.filter(
            mode_paiement='CHEQUE'
        ).aggregate(total=Sum('montant_total'))['total'] or Decimal('0')

        # Le comptage espèces porte sur le contenu physique attendu du tiroir :
        # fonds d'ouverture + ventes espèces de la session.
        especes_attendues = Decimal(str(session.solde_initial or 0)) + Decimal(str(total_especes))
        especes_comptees_val = Decimal(str(especes_comptees))
        carte_val = Decimal(str(montant_carte)) if montant_carte is not None else Decimal(str(total_carte))
        mobile_val = Decimal(str(montant_mobile)) if montant_mobile is not None else Decimal(str(total_mobile))
        cheque_val = Decimal(str(montant_cheque)) if montant_cheque is not None else Decimal(str(total_cheque))
        depot_val = Decimal(str(depot)) if depot is not None else Decimal('0')

        ecart_especes = especes_comptees_val - especes_attendues
        ecart_carte = carte_val - Decimal(str(total_carte))
        ecart_mobile = mobile_val - Decimal(str(total_mobile))
        ecart_cheque = cheque_val - Decimal(str(total_cheque))
        ecart_total = ecart_especes + ecart_carte + ecart_mobile + ecart_cheque

        if (
            abs(ecart_total) > CaisseSessionService.ECART_JUSTIFICATION_SEUIL
            and not (notes or "").strip()
        ):
            raise ValueError(
                "Un motif est obligatoire pour un écart supérieur à 5 000 F."
            )

        session.statut = 'EN_COMPTAGE'
        session.save(update_fields=['statut', 'updated_at'])

        ComptageSession.objects.update_or_create(
            session=session,
            defaults={
                'especes_attendues': especes_attendues,
                'especes_comptees': especes_comptees_val,
                'ecart_especes': ecart_especes,
                'carte_attendue': total_carte,
                'carte_constatee': carte_val,
                'mobile_attendu': total_mobile,
                'mobile_constate': mobile_val,
                'cheque_attendu': total_cheque,
                'cheque_constate': cheque_val,
                'ecart_carte': ecart_carte,
                'ecart_mobile': ecart_mobile,
                'ecart_cheque': ecart_cheque,
                'ecart_total': ecart_total,
                'motif_ecart': (notes or '').strip(),
                'compte_par': fermee_par,
            },
        )

        session.fermee_par = fermee_par
        session.date_fermeture = timezone.now()
        session.statut = 'FERMEE'
        session.notes = notes
        session.save(update_fields=[
            'fermee_par',
            'date_fermeture',
            'statut',
            'notes',
            'updated_at',
        ])

        if depot_val > 0:
            from apps.tresorerie.models import MouvementCaisse
            MouvementCaisse.objects.create(
                caisse=session.caisse,
                type_mouvement='SORTIE',
                montant=depot_val,
                libelle=f"Dépôt clôture session #{session.id}",
                reference=f"DEP-SES-{session.id}",
                created_by=fermee_par.user if fermee_par and fermee_par.user else None,
                date=session.date_fermeture or timezone.now(),
            )

        return {
            'session': session,
            'ecart': ecart_total,
            'ecart_especes': ecart_especes,
            'ecart_carte': ecart_carte,
            'ecart_mobile': ecart_mobile,
            'ecart_cheque': ecart_cheque,
            'especes_attendues': especes_attendues,
            'total_ventes': session.total_ventes,
            'nombre_ventes': session.nombre_ventes,
        }

    @staticmethod
    @transaction.atomic
    def valider_session(session, validee_par):
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        if session.statut != 'FERMEE':
            raise ValueError("Seule une session fermée peut être validée.")
        if not validee_par or not validee_par.actif:
            raise ValueError("Un validateur actif est obligatoire.")

        session.statut = 'VALIDEE'
        session.validee_par = validee_par
        session.date_validation = timezone.now()
        session.save(update_fields=[
            'statut',
            'validee_par',
            'date_validation',
            'updated_at',
        ])
        return session

    @staticmethod
    @transaction.atomic
    def annuler_session(session):
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        if session.statut not in ('OUVERTE',):
            raise ValueError("Seules les sessions ouvertes sans op\u00e9ration peuvent \u00eatre annul\u00e9es")
        if session.total_ventes > 0:
            raise ValueError("Impossible d'annuler une session avec des ventes")
        session.statut = 'ANNULEE'
        session.notes = (session.notes or '') + " | ANNUL\u00c9E"
        session.save()

        if hasattr(session, 'comptage'):
            session.comptage.delete()
        return session

    @staticmethod
    def get_session_active(caisse):
        return SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').first()

    @staticmethod
    def get_historique_par_caissier(caissier, jours=30):
        depuis = timezone.now() - timedelta(days=jours)
        sessions_ouvertes = SessionCaisse.objects.filter(ouverte_par=caissier, date_ouverture__gte=depuis)
        sessions_fermees = SessionCaisse.objects.filter(fermee_par=caissier, date_fermeture__gte=depuis)
        return {
            'ouvertes': sessions_ouvertes,
            'fermees': sessions_fermees,
            'total_ventes': Vente.objects.filter(caissier=caissier, created_at__gte=depuis).count(),
            'ca_total': Vente.objects.filter(caissier=caissier, created_at__gte=depuis, statut='PAYEE').aggregate(
                total=Sum('montant_total')
            )['total'] or 0,
        }

    @staticmethod
    def get_rapport_journalier(caisse, date=None):
        if not date:
            date = timezone.now().date()
        sessions = SessionCaisse.objects.filter(caisse=caisse, date_ouverture__date=date)
        return {
            'date': date,
            'sessions': sessions,
            'total_sessions': sessions.count(),
            'total_ventes': sum(s.nombre_ventes for s in sessions),
            'ca_total': sum(s.total_ventes for s in sessions),
        }

    @staticmethod
    def get_session_top_produits(session, limit=10):
        from apps.pos.models import LigneVente
        lignes = LigneVente.objects.filter(vente__session_caisse=session, vente__statut='PAYEE')
        from django.db.models import F, Value, Case, When, CharField
        top = (
            lignes
            .annotate(
                article_nom=Case(
                    When(produit__isnull=False, then=F('produit__nom')),
                    When(menu__isnull=False, then=F('menu__nom')),
                    default=Value('Inconnu'), output_field=CharField(),
                ),
                article_type=Case(
                    When(produit__isnull=False, then=Value('PRODUIT')),
                    When(menu__isnull=False, then=Value('MENU')),
                    default=Value('AUTRE'), output_field=CharField(),
                ),
                ligne_total=F('quantite') * F('prix_unitaire'),
            )
            .values('article_nom', 'article_type')
            .annotate(quantite=Sum('quantite'), montant=Sum('ligne_total'))
            .order_by('-quantite')[:limit]
        )
        return [
            {'nom': t['article_nom'], 'type': t['article_type'],
             'quantite': float(t['quantite']), 'montant': float(t['montant'])}
            for t in top
        ]

    @staticmethod
    def get_session_produit_list(session):
        from apps.pos.models import LigneVente
        lignes = LigneVente.objects.filter(vente__session_caisse=session)
        from django.db.models import F, CharField, Value, Case, When
        qs = (
            lignes
            .annotate(
                article_nom=Case(
                    When(produit__isnull=False, then=F('produit__nom')),
                    When(menu__isnull=False, then=F('menu__nom')),
                    default=Value('Inconnu'), output_field=CharField(),
                ),
                article_id=Case(
                    When(produit__isnull=False, then=F('produit__id')),
                    When(menu__isnull=False, then=F('menu__id')),
                    default=Value(0), output_field=CharField(),
                ),
            )
            .values('article_nom', 'article_id')
            .distinct()
            .order_by('article_nom')
        )
        return list(qs)

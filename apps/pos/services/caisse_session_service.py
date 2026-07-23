# apps/pos/services/caisse_session_service.py
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from decimal import Decimal
from datetime import datetime, timedelta
from apps.pos.models import SessionCaisse, ChangementCaissier, Vente, SessionPlanning
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse


def get_session_autorisee(session_id, user, require_open=False):
    """Retourne une session si l'utilisateur y a accès, sinon PermissionDenied."""
    from django.core.exceptions import PermissionDenied
    from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF
    employe = getattr(user, 'employe', None)
    qs = SessionCaisse.objects.filter(id=session_id)
    if not user.is_superuser and not user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        if not employe or not employe.point_vente_id:
            raise PermissionDenied("Aucun point de vente associé")
        qs = qs.filter(point_vente_id=employe.point_vente_id)
    session = qs.first()
    if session is None:
        raise PermissionDenied("Session introuvable ou accès non autorisé")
    if require_open and session.statut != 'OUVERTE':
        raise PermissionDenied("Cette session est déjà clôturée")
    return session


def get_session_ouverte_pv(point_vente):
    """Session OUVERTE sur la caisse du point de vente, ou None.
    Verrou central : aucune commande/vente ne doit passer sans elle."""
    if not point_vente or not point_vente.caisse_id:
        return None
    return SessionCaisse.objects.filter(
        caisse_id=point_vente.caisse_id, statut='OUVERTE'
    ).first()


def get_planning_actif(employe, point_vente):
    """Retourne le planning actif pour cet employé/point de vente à l'instant présent, ou None"""
    if not employe or not point_vente:
        return None
    now = timezone.localtime()
    aujourdhui = now.date()
    heure_courante = now.time()

    plannings = SessionPlanning.objects.filter(
        employe=employe,
        point_vente=point_vente,
        date=aujourdhui,
    ).exclude(statut='ANNULE')

    for p in plannings:
        if p.heure_debut == p.heure_fin:
            return p
        if p.heure_debut < p.heure_fin:
            if p.heure_debut <= heure_courante <= p.heure_fin:
                return p
        else:
            if heure_courante >= p.heure_debut:
                return p

    hier = aujourdhui - timedelta(days=1)
    yesterday_plannings = SessionPlanning.objects.filter(
        employe=employe,
        point_vente=point_vente,
        date=hier,
    ).exclude(statut='ANNULE')

    for p in yesterday_plannings:
        if p.heure_debut >= p.heure_fin and heure_courante <= p.heure_fin:
            return p

    return None


class CaisseSessionService:
    """Service de gestion des sessions de caisse"""

    @staticmethod
    @transaction.atomic
    def ouverture_session(caisse, point_vente, caissier, debut_prevu=None, fin_prevu=None, planning=None):
        """Ouvre une nouvelle session de caisse - solde_initial = solde caisse.

        Si une session est deja ouverte sur cette caisse pour LE MEME planning,
        elle est reutilisee (reconnexion sur le meme shift). Si elle est liee a
        un planning different (ou absent), c'est une session perimee laissee
        ouverte par erreur : on la ferme automatiquement avant d'en ouvrir une
        nouvelle, plutot que de silencieusement lui accrocher le nouveau planning
        (ce qui masquait les sessions oubliees ouvertes depuis des jours)."""
        caisse_verrouillee = Caisse.objects.select_for_update().get(pk=caisse.pk)
        session_ouverte = SessionCaisse.objects.select_for_update().filter(
            caisse=caisse_verrouillee,
            statut='OUVERTE'
        ).first()

        if session_ouverte:
            meme_planning = planning is not None and session_ouverte.planning_id == planning.id
            if meme_planning:
                session_ouverte.caissier_ouverture = caissier
                session_ouverte.debut_prevu = debut_prevu
                session_ouverte.fin_prevu = fin_prevu
                session_ouverte.save()
                return session_ouverte

            CaisseSessionService.fermeture_automatique(session_ouverte, session_ouverte.caissier_ouverture)
            caisse_verrouillee.refresh_from_db()

        solde_initial = caisse_verrouillee.solde

        session = SessionCaisse.objects.create(
            caisse=caisse_verrouillee,
            point_vente=point_vente,
            caissier_ouverture=caissier,
            solde_initial=solde_initial,
            solde_attendu=solde_initial,
            debut_prevu=debut_prevu,
            fin_prevu=fin_prevu,
            planning=planning,
            statut='OUVERTE'
        )

        return session


    @staticmethod
    @transaction.atomic
    def changement_caissier(session, nouveau_caissier, raison=""):
        """Change de caissier pendant une session active"""
        if session.statut != 'OUVERTE':
            raise ValueError("La session n'est pas ouverte")

        ancien_caissier = session.caissier_ouverture

        ChangementCaissier.objects.create(
            session=session,
            ancien_caissier=ancien_caissier,
            nouveau_caissier=nouveau_caissier,
            raison=raison
        )

        session.caissier_ouverture = nouveau_caissier
        session.save()

        return session

    @staticmethod
    @transaction.atomic
    def fermeture_session(session, solde_reel, caissier_fermeture, notes="", depot=None):
        """Ferme une session de caisse avec comptage réel - tout est atomique et annulable."""
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        if session.statut != 'OUVERTE':
            raise ValueError("La session n'est pas ouverte")

        session.calculer_solde_attendu()

        ventes_session = Vente.objects.filter(session_caisse=session, statut='PAYEE')
        session.total_especes = ventes_session.filter(mode_paiement='ESPECES').aggregate(total=Sum('montant_total'))['total'] or 0
        session.total_carte = ventes_session.filter(mode_paiement='CARTE').aggregate(total=Sum('montant_total'))['total'] or 0
        session.total_mobile_money = ventes_session.filter(mode_paiement='MOBILE_MONEY').aggregate(total=Sum('montant_total'))['total'] or 0
        session.total_compte_client = ventes_session.filter(mode_paiement='COMPTE_CLIENT').aggregate(total=Sum('montant_total'))['total'] or 0

        depot_val = Decimal(str(depot)) if depot is not None else None
        difference = session.fermer(solde_reel, caissier_fermeture, notes, depot_val)

        caisse = session.caisse
        if depot_val and depot_val > 0:
            from apps.tresorerie.models import MouvementCaisse, TransfertCaisse
            MouvementCaisse.objects.create(
                caisse=caisse,
                type_mouvement='SORTIE',
                montant=depot_val,
                libelle=f"Dépôt clôture session #{session.id}",
                reference=f"DEP-SES-{session.id}",
                created_by=caissier_fermeture.user if caissier_fermeture and caissier_fermeture.user else None,
                date=session.date_fermeture or timezone.now(),
            )
            if caisse.caisse_centrale:
                ref = f"DEP-SES-{session.id}-{timezone.now().strftime('%y%m%d%H%M')}"
                TransfertCaisse.objects.create(
                    source=caisse,
                    destination=caisse.caisse_centrale,
                    montant=depot_val,
                    reference=ref,
                    valide_par=caissier_fermeture.user if caissier_fermeture and caissier_fermeture.user else None,
                    notes=f"Dépôt session #{session.id} — {session.point_vente.nom if session.point_vente else ''}",
                )
                caisse.caisse_centrale.solde += depot_val
                caisse.caisse_centrale.save()

        if difference != 0:
            from apps.tresorerie.models import MouvementCaisse
            user = caissier_fermeture.user if caissier_fermeture and caissier_fermeture.user else None
            MouvementCaisse.objects.create(
                caisse=caisse,
                type_mouvement='AJUSTEMENT',
                montant=abs(difference),
                libelle=f"Ajustement session #{session.id} — {'Excédent' if difference > 0 else 'Déficit'}",
                reference=f"ECART-SES-{session.id}",
                created_by=user,
                date=session.date_fermeture or timezone.now(),
            )

        if abs(difference) > 5000:
            session.notes = f"Écart important: {difference} F. {notes}"
            session.save()

        return {
            'session': session,
            'solde_attendu': session.solde_attendu,
            'solde_reel': session.solde_reel,
            'depot': session.depot,
            'solde_restant': session.solde_restant,
            'difference': difference,
            'total_ventes': session.total_ventes,
            'nombre_ventes': session.nombre_ventes
        }

    @staticmethod
    @transaction.atomic
    def fermeture_automatique(session, caissier_fermeture):
        """Ferme automatiquement une session sans comptage réel (fin de planning).
        Utilise solde_attendu comme solde_reel, aucun ajustement."""
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        if session.statut != 'OUVERTE':
            raise ValueError("La session n'est pas ouverte")

        session.calculer_solde_attendu()

        ventes_session = Vente.objects.filter(session_caisse=session, statut='PAYEE')
        session.total_especes = ventes_session.filter(mode_paiement='ESPECES').aggregate(total=Sum('montant_total'))['total'] or 0
        session.total_carte = ventes_session.filter(mode_paiement='CARTE').aggregate(total=Sum('montant_total'))['total'] or 0
        session.total_mobile_money = ventes_session.filter(mode_paiement='MOBILE_MONEY').aggregate(total=Sum('montant_total'))['total'] or 0
        session.total_compte_client = ventes_session.filter(mode_paiement='COMPTE_CLIENT').aggregate(total=Sum('montant_total'))['total'] or 0

        planning_info = ""
        if session.planning:
            p = session.planning
            planning_info = f" (planning {p.date} {p.heure_debut}-{p.heure_fin})"

        notes = f"Fermeture automatique fin de planning{planning_info}"
        difference = session.fermer(
            solde_reel=session.solde_attendu,
            caissier_fermeture=caissier_fermeture,
            notes=notes,
            depot=0,
        )

        return {
            'session': session,
            'solde_attendu': session.solde_attendu,
            'solde_reel': session.solde_reel,
            'difference': difference,
        }

    @staticmethod
    @transaction.atomic
    def annuler_fermeture(session, caissier):
        """Annule proprement une fermeture de session :
        - Remet statut = OUVERTE
        - Supprime les mouvements (dépôt, ajustement) créés par la fermeture
        - Annule les transferts vers la centrale
        - Restaure le solde de la centrale
        - Remet le solde de la caisse au solde_restant avant annulation
        """
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        if session.statut != 'FERMEE':
            raise ValueError("Seules les sessions fermées peuvent être annulées")

        from apps.tresorerie.models import MouvementCaisse, TransfertCaisse

        caisse = Caisse.objects.select_for_update().get(pk=session.caisse.pk)

        ancien_solde_caisse = caisse.solde

        if session.depot and session.depot > 0 and caisse.caisse_centrale:
            centrale = Caisse.objects.select_for_update().get(pk=caisse.caisse_centrale.pk)
            centrale.solde -= session.depot
            centrale.save()

        MouvementCaisse.objects.filter(
            reference__in=[f"DEP-SES-{session.id}", f"ECART-SES-{session.id}"]
        ).delete()

        TransfertCaisse.objects.filter(reference__startswith=f"DEP-SES-{session.id}").delete()

        session.statut = 'OUVERTE'
        session.date_fermeture = None
        session.caissier_fermeture = None
        session.solde_reel = None
        session.depot = 0
        session.difference = 0
        session.solde_restant = ancien_solde_caisse
        session.notes = f"ANNULÉE: {session.notes}" if session.notes else "ANNULÉE"
        session.save()

        caisse.solde = ancien_solde_caisse
        caisse.save()

        return session

    @staticmethod
    def verifier_session_planning(caisse, employe, point_vente):
        """Détecte l'état de la session au chargement du POS sans rien modifier.
        Retourne un dict:
          - session_active: SessionCaisse | None
          - planning_expire: bool — la session active a un planning terminé
          - session_a_fermer: dict | None — infos de la session à fermer (id, total_ventes, planning)
          - nouveau_planning: dict | None — infos du nouveau planning si actif
          - planning_actif: SessionPlanning | None
        """
        now = timezone.localtime()
        session_active = SessionCaisse.objects.filter(
            caisse=caisse, statut='OUVERTE'
        ).first()

        result = {
            'session_active': session_active,
            'planning_expire': False,
            'session_a_fermer': None,
            'nouveau_planning': None,
            'planning_actif': None,
        }

        # Vérifier si la session active a un planning expiré
        if session_active and session_active.planning:
            planning = session_active.planning
            planning_termine = False

            if planning.heure_debut == planning.heure_fin:
                pass
            else:
                planning_fin = datetime.combine(planning.date, planning.heure_fin)
                if planning.heure_debut > planning.heure_fin:
                    planning_fin += timedelta(days=1)
                planning_fin = timezone.make_aware(planning_fin, timezone.get_current_timezone())
                if now > planning_fin:
                    planning_termine = True

            if planning_termine:
                total_ventes = Vente.objects.filter(
                    session_caisse=session_active, statut='PAYEE'
                ).aggregate(total=Sum('montant_total'))['total'] or 0
                result['planning_expire'] = True
                result['session_a_fermer'] = {
                    'id': session_active.id,
                    'total_ventes': float(total_ventes),
                    'planning_date': planning.date.strftime('%d/%m/%Y'),
                    'planning_debut': planning.heure_debut.strftime('%H:%M'),
                    'planning_fin': planning.heure_fin.strftime('%H:%M'),
                    'point_vente': session_active.point_vente.nom if session_active.point_vente else '',
                }

        # Détecter nouveau planning actif
        planning_actif = get_planning_actif(employe, point_vente)
        result['planning_actif'] = planning_actif
        if planning_actif and (not session_active or result['planning_expire']):
            result['nouveau_planning'] = {
                'id': planning_actif.id,
                'date': planning_actif.date.strftime('%d/%m/%Y'),
                'debut': planning_actif.heure_debut.strftime('%H:%M'),
                'fin': planning_actif.heure_fin.strftime('%H:%M'),
                'point_vente': planning_actif.point_vente.nom if planning_actif.point_vente else '',
                'solde_initial': float(caisse.solde),
            }

        return result

    @staticmethod
    @transaction.atomic
    def fermer_et_preparer_prochaine(session, caissier, point_vente):
        """Ferme la session (solde_attendu = solde_reel) et ouvre la suivante
        si un planning actif existe pour ce caissier/point_vente.
        Retourne { session_fermee, nouvelle_session, nouveau_planning }.
        """
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        fermee = CaisseSessionService.fermeture_automatique(session, caissier)

        nouvelle_session = None
        nouveau_planning = get_planning_actif(caissier, point_vente)
        if nouveau_planning:
            nouvelle_session = CaisseSessionService.ouverture_session(
                caisse=session.caisse,
                point_vente=point_vente,
                caissier=caissier,
                debut_prevu=nouveau_planning.heure_debut,
                fin_prevu=nouveau_planning.heure_fin,
                planning=nouveau_planning,
            )

        return {
            'session_fermee': fermee['session'],
            'nouvelle_session': nouvelle_session,
            'nouveau_planning': nouveau_planning,
        }

    @staticmethod
    def get_session_active(caisse):
        """Récupère la session active pour une caisse"""
        return SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').first()

    @staticmethod
    def get_historique_par_caissier(caissier, jours=30):
        """Récupère l'historique des sessions pour un caissier"""
        depuis = timezone.now() - timedelta(days=jours)

        sessions_ouvertes = SessionCaisse.objects.filter(
            caissier_ouverture=caissier,
            date_ouverture__gte=depuis
        )

        sessions_fermees = SessionCaisse.objects.filter(
            caissier_fermeture=caissier,
            date_fermeture__gte=depuis
        )

        return {
            'ouvertes': sessions_ouvertes,
            'fermees': sessions_fermees,
            'total_ventes': Vente.objects.filter(caissier=caissier, created_at__gte=depuis).count(),
            'ca_total': Vente.objects.filter(caissier=caissier, created_at__gte=depuis, statut='PAYEE').aggregate(total=Sum('montant_total'))['total'] or 0
        }

    @staticmethod
    def get_rapport_journalier(caisse, date=None):
        """Rapport quotidien des sessions"""
        if not date:
            date = timezone.now().date()

        sessions = SessionCaisse.objects.filter(
            caisse=caisse,
            date_ouverture__date=date
        )

        return {
            'date': date,
            'sessions': sessions,
            'total_sessions': sessions.count(),
            'total_ventes': sum(s.nombre_ventes for s in sessions),
            'ca_total': sum(s.total_ventes for s in sessions),
            'ecart_total': sum(s.difference for s in sessions if s.difference)
        }

    @staticmethod
    def get_session_top_produits(session, limit=10):
        """Top produits les plus vendus dans une session (produits + menus)."""
        from apps.pos.models import LigneVente
        lignes = LigneVente.objects.filter(vente__session_caisse=session, vente__statut='PAYEE')
        from django.db.models import F, Sum, Value, Case, When, CharField
        top = (
            lignes
            .annotate(
                article_nom=Case(
                    When(produit__isnull=False, then=F('produit__nom')),
                    When(menu__isnull=False, then=F('menu__nom')),
                    default=Value('Inconnu'),
                    output_field=CharField(),
                ),
                article_type=Case(
                    When(produit__isnull=False, then=Value('PRODUIT')),
                    When(menu__isnull=False, then=Value('MENU')),
                    default=Value('AUTRE'),
                    output_field=CharField(),
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
        """Liste des produits/menus distincts pour le filtre."""
        from apps.pos.models import LigneVente
        lignes = LigneVente.objects.filter(vente__session_caisse=session)
        from django.db.models import F, CharField, Value, Case, When
        qs = (
            lignes
            .annotate(
                article_nom=Case(
                    When(produit__isnull=False, then=F('produit__nom')),
                    When(menu__isnull=False, then=F('menu__nom')),
                    default=Value('Inconnu'),
                    output_field=CharField(),
                ),
                article_id=Case(
                    When(produit__isnull=False, then=F('produit__id')),
                    When(menu__isnull=False, then=F('menu__id')),
                    default=Value(0),
                    output_field=CharField(),
                ),
            )
            .values('article_nom', 'article_id')
            .distinct()
            .order_by('article_nom')
        )
        return list(qs)

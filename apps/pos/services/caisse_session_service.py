from django.utils import timezone
from django.db import transaction
from django.db.models import Sum, Q
from decimal import Decimal
from datetime import timedelta

from apps.pos.models import SessionCaisse, Vente, ComptageSession, CaissePointVente, AffectationPointVente
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse


def get_session_autorisee(session_id, user, require_open=False):
    from django.core.exceptions import PermissionDenied
    from apps.authentication.groups import PATRON, MANAGER, COMPTABLE, RAF
    qs = SessionCaisse.objects.filter(id=session_id)
    if not user.is_superuser and not user.groups.filter(name__in=[PATRON, MANAGER, COMPTABLE, RAF]).exists():
        employe = getattr(user, 'employe', None)
        if not employe:
            raise PermissionDenied("Aucun employ\u00e9 associ\u00e9")
        pv_ids = AffectationPointVente.objects.filter(employe=employe, actif=True).values_list('point_vente_id', flat=True)
        qs = qs.filter(point_vente_id__in=pv_ids)
    session = qs.first()
    if session is None:
        raise PermissionDenied("Session introuvable ou acc\u00e8s non autoris\u00e9")
    if require_open and session.statut not in ('OUVERTE', 'EN_COMPTAGE'):
        raise PermissionDenied("Cette session n'est plus ouverte")
    return session


def get_session_active_caisse(caisse):
    if not caisse:
        return None
    return SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').first()


def get_session_active_pv(point_vente):
    if not point_vente:
        return None
    cpv = CaissePointVente.objects.filter(point_vente=point_vente, actif=True).select_related('caisse').first()
    if not cpv:
        return None
    return get_session_active_caisse(cpv.caisse)


class CaisseSessionService:

    @staticmethod
    @transaction.atomic
    def ouverture_session(caisse, point_vente, caissier, shift=None):
        caisse_verrouillee = Caisse.objects.select_for_update().get(pk=caisse.pk)
        session_active = SessionCaisse.objects.select_for_update().filter(
            caisse=caisse_verrouillee,
            statut__in=['OUVERTE', 'EN_COMPTAGE'],
        ).first()

        if session_active:
            raise ValueError(
                "La caisse poss\u00e8de d\u00e9j\u00e0 une session non finalis\u00e9e. "
                "Fermez ou validez la session pr\u00e9c\u00e9dente."
            )

        session = SessionCaisse.objects.create(
            caisse=caisse_verrouillee,
            point_vente=point_vente,
            ouverte_par=caissier,
            solde_initial=caisse_verrouillee.solde,
            shift=shift,
            statut='OUVERTE',
        )
        return session

    @staticmethod
    @transaction.atomic
    def fermeture_session(session, especes_comptees, fermee_par, notes='',
                          montant_carte=None, montant_mobile=None, montant_cheque=None,
                          depot=None):
        session = SessionCaisse.objects.select_for_update().get(pk=session.pk)
        if session.statut not in ('OUVERTE', 'EN_COMPTAGE'):
            raise ValueError("La session n'est pas ouverte/en comptage")

        session.statut = 'EN_COMPTAGE'
        session.save(update_fields=['statut'])

        ventes = Vente.objects.filter(session_caisse=session, statut='PAYEE')
        total_especes = ventes.filter(mode_paiement='ESPECES').aggregate(total=Sum('montant_total'))['total'] or 0
        total_carte = ventes.filter(
            mode_paiement__in=['CARTE', 'VISA', 'MASTERCARD']
        ).aggregate(total=Sum('montant_total'))['total'] or 0
        total_mobile = ventes.filter(mode_paiement='MOBILE_MONEY').aggregate(total=Sum('montant_total'))['total'] or 0
        total_cheque = ventes.filter(mode_paiement='CHEQUE').aggregate(total=Sum('montant_total'))['total'] or 0

        carte_val = Decimal(str(montant_carte)) if montant_carte is not None else total_carte
        mobile_val = Decimal(str(montant_mobile)) if montant_mobile is not None else total_mobile
        cheque_val = Decimal(str(montant_cheque)) if montant_cheque is not None else total_cheque
        depot_val = Decimal(str(depot)) if depot is not None else Decimal('0')

        ecart = Decimal(str(especes_comptees)) - total_especes

        ComptageSession.objects.create(
            session=session,
            especes_attendues=total_especes,
            especes_comptees=especes_comptees,
            ecart_especes=ecart,
            carte_attendue=total_carte,
            carte_constatee=carte_val,
            mobile_attendu=total_mobile,
            mobile_constate=mobile_val,
            cheque_attendu=total_cheque,
            cheque_constate=cheque_val,
            motif_ecart=notes if abs(ecart) > 5000 else '',
            compte_par=fermee_par,
        )

        session.fermee_par = fermee_par
        session.date_fermeture = timezone.now()
        session.statut = 'FERMEE'
        session.notes = notes
        session.save()

        if depot_val > 0:
            from apps.tresorerie.models import MouvementCaisse
            MouvementCaisse.objects.create(
                caisse=session.caisse, type_mouvement='SORTIE', montant=depot_val,
                libelle=f"D\u00e9p\u00f4t cl\u00f4ture session #{session.id}",
                reference=f"DEP-SES-{session.id}",
                created_by=fermee_par.user if fermee_par and fermee_par.user else None,
                date=session.date_fermeture or timezone.now(),
            )

        return {
            'session': session,
            'ecart': ecart,
            'total_ventes': session.total_ventes,
            'nombre_ventes': session.nombre_ventes,
        }

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

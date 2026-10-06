from dataclasses import dataclass
from datetime import datetime, timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.utils import timezone

from apps.authentication.groups import MANAGER, PATRON
from apps.pos.constants import (
    ActionPOS,
    ModeAccesPOS,
    POINTS_VENTE_OPERATIONNELS,
)
from apps.pos.models import (
    AffectationPointVente,
    HoraireAffectation,
    PointVente,
    ShiftEmploye,
)


ACTION_PERMISSION_FIELDS = {
    ActionPOS.ACCEDER: None,
    ActionPOS.VENDRE: "peut_vendre",
    ActionPOS.ENCAISSER: "peut_encaisser",
    ActionPOS.OUVRIR_CAISSE: "peut_ouvrir_caisse",
    ActionPOS.FERMER_CAISSE: "peut_fermer_caisse",
    ActionPOS.ANNULER_VENTE: "peut_annuler_vente",
    ActionPOS.ACCORDER_REMISE: "peut_accorder_remise",
    ActionPOS.CONSULTER_RAPPORTS: "peut_consulter_rapports",
}


@dataclass(frozen=True)
class POSAccessDecision:
    allowed: bool
    reason: str
    mode: str | None = None
    action: str = ActionPOS.ACCEDER
    point_vente_id: int | None = None
    affectation_id: int | None = None
    shift_id: int | None = None
    horaire_id: int | None = None
    expires_at: datetime | None = None

    def to_dict(self):
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "mode": self.mode,
            "action": self.action,
            "point_vente_id": self.point_vente_id,
            "affectation_id": self.affectation_id,
            "shift_id": self.shift_id,
            "horaire_id": self.horaire_id,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
        }


class POSAccessDenied(PermissionDenied):
    def __init__(self, decision: POSAccessDecision):
        self.decision = decision
        super().__init__(decision.reason)


class POSAccessService:
    """Autorité unique d'accès aux POS Bar / Restaurant.

    Ordre de décision :
    1. le point de vente appartient au périmètre Bar/Restaurant ;
    2. l'employé est actif ;
    3. direction/superuser ou affectation TOTAL ;
    4. affectation au point de vente ;
    5. mode PERMANENT / HORAIRES / PLANNING ;
    6. permission métier demandée.

    Une vue ne doit plus déduire un accès à partir d'un groupe, d'un pointage
    ou de l'existence brute d'une affectation.
    """

    GROUPES_ACCES_TOTAL = (PATRON, MANAGER)

    @classmethod
    def check(
        cls,
        *,
        point_vente,
        action=ActionPOS.ACCEDER,
        user=None,
        employe=None,
        moment=None,
    ) -> POSAccessDecision:
        moment = cls._normaliser_moment(moment)
        point_vente = cls._point(point_vente)

        if point_vente is None:
            return cls._deny("POINT_VENTE_INTROUVABLE", action=action)

        if not point_vente.actif:
            return cls._deny(
                "POINT_VENTE_INACTIF",
                action=action,
                point_vente=point_vente,
            )

        if point_vente.type not in POINTS_VENTE_OPERATIONNELS:
            return cls._deny(
                "HORS_PERIMETRE_POS_BAR_RESTAURANT",
                action=action,
                point_vente=point_vente,
            )

        if employe is None and user is not None:
            employe = getattr(user, "employe", None)
        if user is None and employe is not None:
            user = getattr(employe, "user", None)

        # Direction : accès réellement global au moteur Vente/POS Bar+Restaurant.
        if user is not None and (
            user.is_superuser
            or user.groups.filter(name__in=cls.GROUPES_ACCES_TOTAL).exists()
        ):
            return POSAccessDecision(
                allowed=True,
                reason="ACCES_TOTAL_DIRECTION",
                mode=ModeAccesPOS.TOTAL,
                action=action,
                point_vente_id=point_vente.id,
            )

        if employe is None:
            return cls._deny(
                "AUCUN_PROFIL_EMPLOYE",
                action=action,
                point_vente=point_vente,
            )
        if not employe.actif:
            return cls._deny(
                "EMPLOYE_INACTIF",
                action=action,
                point_vente=point_vente,
            )

        affectations = list(
            AffectationPointVente.objects.filter(
                employe=employe,
                actif=True,
            )
            .filter(
                Q(date_debut__isnull=True) | Q(date_debut__lte=moment.date()),
                Q(date_fin__isnull=True) | Q(date_fin__gte=moment.date()),
            )
            .select_related("point_vente")
            .order_by("-principal", "id")
        )

        # Une affectation TOTAL vaut sur tous les POS opérationnels.
        total_candidates = [
            a for a in affectations if a.mode_acces == ModeAccesPOS.TOTAL
        ]
        point_candidates = [
            a
            for a in affectations
            if a.point_vente_id == point_vente.id
            and a.mode_acces != ModeAccesPOS.TOTAL
        ]

        candidates = total_candidates + point_candidates
        if not candidates:
            return cls._deny(
                "AUCUNE_AFFECTATION_POS",
                action=action,
                point_vente=point_vente,
            )

        permission_refusee = False
        hors_creneau = False

        for affectation in candidates:
            if not cls._permission_ok(affectation, action):
                permission_refusee = True
                continue

            if affectation.mode_acces in (
                ModeAccesPOS.TOTAL,
                ModeAccesPOS.PERMANENT,
            ):
                return POSAccessDecision(
                    allowed=True,
                    reason=(
                        "ACCES_TOTAL_AFFECTATION"
                        if affectation.mode_acces == ModeAccesPOS.TOTAL
                        else "ACCES_PERMANENT"
                    ),
                    mode=affectation.mode_acces,
                    action=action,
                    point_vente_id=point_vente.id,
                    affectation_id=affectation.id,
                )

            if affectation.mode_acces == ModeAccesPOS.HORAIRES:
                horaire, expiration = cls._horaire_actif(affectation, moment)
                if horaire is None:
                    hors_creneau = True
                    continue
                return POSAccessDecision(
                    allowed=True,
                    reason="HORAIRE_ACTIF",
                    mode=ModeAccesPOS.HORAIRES,
                    action=action,
                    point_vente_id=point_vente.id,
                    affectation_id=affectation.id,
                    horaire_id=horaire.id,
                    expires_at=expiration,
                )

            if affectation.mode_acces == ModeAccesPOS.PLANNING:
                shift = cls._shift_actif(affectation, moment)
                if shift is None:
                    hors_creneau = True
                    continue
                return POSAccessDecision(
                    allowed=True,
                    reason="PLANNING_ACTIF",
                    mode=ModeAccesPOS.PLANNING,
                    action=action,
                    point_vente_id=point_vente.id,
                    affectation_id=affectation.id,
                    shift_id=shift.id,
                    expires_at=shift.fin_prevue,
                )

        if permission_refusee and not hors_creneau:
            return cls._deny(
                "PERMISSION_METIER_REFUSEE",
                action=action,
                point_vente=point_vente,
            )
        if hors_creneau:
            return cls._deny(
                "HORS_CRENEAU_AUTORISE",
                action=action,
                point_vente=point_vente,
            )
        return cls._deny(
            "ACCES_REFUSE",
            action=action,
            point_vente=point_vente,
        )

    @classmethod
    def check_capability(
        cls,
        *,
        point_vente,
        action,
        user=None,
        employe=None,
        moment=None,
    ) -> POSAccessDecision:
        """Vérifie une capacité métier sans appliquer la fenêtre horaire.

        Usage volontairement limité aux opérations de finalisation d'un état
        déjà engagé, notamment fermer/compter une session ouverte avant
        l'expiration du shift. Cette méthode ne doit pas être utilisée pour
        vendre ou encaisser hors créneau.
        """
        moment = cls._normaliser_moment(moment)
        point_vente = cls._point(point_vente)

        if point_vente is None:
            return cls._deny("POINT_VENTE_INTROUVABLE", action=action)
        if not point_vente.actif:
            return cls._deny(
                "POINT_VENTE_INACTIF",
                action=action,
                point_vente=point_vente,
            )
        if point_vente.type not in POINTS_VENTE_OPERATIONNELS:
            return cls._deny(
                "HORS_PERIMETRE_POS_BAR_RESTAURANT",
                action=action,
                point_vente=point_vente,
            )

        if employe is None and user is not None:
            employe = getattr(user, "employe", None)
        if user is None and employe is not None:
            user = getattr(employe, "user", None)

        if user is not None and (
            user.is_superuser
            or user.groups.filter(name__in=cls.GROUPES_ACCES_TOTAL).exists()
        ):
            return POSAccessDecision(
                allowed=True,
                reason="CAPACITE_TOTAL_DIRECTION",
                mode=ModeAccesPOS.TOTAL,
                action=action,
                point_vente_id=point_vente.id,
            )

        if employe is None:
            return cls._deny(
                "AUCUN_PROFIL_EMPLOYE",
                action=action,
                point_vente=point_vente,
            )
        if not employe.actif:
            return cls._deny(
                "EMPLOYE_INACTIF",
                action=action,
                point_vente=point_vente,
            )

        # Finalisation d'une session déjà engagée : on conserve la
        # capacité métier historique même si l'affectation vient d'expirer ou
        # d'être désactivée. Ce chemin ne permet ni vente ni encaissement.
        affectations = list(
            AffectationPointVente.objects.filter(
                employe=employe,
            )
            .select_related("point_vente")
            .order_by("-actif", "-principal", "id")
        )
        candidates = [
            a
            for a in affectations
            if a.mode_acces == ModeAccesPOS.TOTAL
            or a.point_vente_id == point_vente.id
        ]
        if not candidates:
            return cls._deny(
                "AUCUNE_AFFECTATION_POS",
                action=action,
                point_vente=point_vente,
            )

        for affectation in candidates:
            if cls._permission_ok(affectation, action):
                return POSAccessDecision(
                    allowed=True,
                    reason="CAPACITE_METIER_ACTIVE",
                    mode=affectation.mode_acces,
                    action=action,
                    point_vente_id=point_vente.id,
                    affectation_id=affectation.id,
                )

        return cls._deny(
            "PERMISSION_METIER_REFUSEE",
            action=action,
            point_vente=point_vente,
        )

    @classmethod
    def assert_allowed(cls, **kwargs) -> POSAccessDecision:
        decision = cls.check(**kwargs)
        if not decision.allowed:
            raise POSAccessDenied(decision)
        return decision

    @classmethod
    def can(cls, **kwargs) -> bool:
        return cls.check(**kwargs).allowed

    @classmethod
    def points_accessibles(
        cls,
        *,
        user,
        action=ActionPOS.ACCEDER,
        moment=None,
    ):
        qs = PointVente.objects.filter(
            actif=True,
            type__in=POINTS_VENTE_OPERATIONNELS,
        ).order_by("type", "nom")
        ids = [
            point.id
            for point in qs
            if cls.check(
                user=user,
                point_vente=point,
                action=action,
                moment=moment,
            ).allowed
        ]
        return qs.filter(id__in=ids)

    @classmethod
    def _permission_ok(cls, affectation, action):
        champ = ACTION_PERMISSION_FIELDS.get(action)
        if champ is None:
            return action == ActionPOS.ACCEDER
        return bool(getattr(affectation, champ, False))

    @staticmethod
    def _shift_actif(affectation, moment):
        return (
            ShiftEmploye.objects.filter(
                affectation=affectation,
                debut_prevu__lte=moment,
                fin_prevue__gte=moment,
                statut__in=("PLANIFIE", "CONFIRME", "EN_COURS"),
            )
            .order_by("fin_prevue")
            .first()
        )

    @classmethod
    def _horaire_actif(cls, affectation, moment):
        """Retourne (horaire, expiration).

        Les créneaux traversant minuit sont gérés sur deux jours :
        vendredi 18:00 -> 02:00 autorise samedi à 01:00.
        """
        today = moment.date()
        local_time = moment.timetz().replace(tzinfo=None)

        horaires = list(
            HoraireAffectation.objects.filter(
                affectation=affectation,
                actif=True,
            ).order_by("jour_semaine", "heure_debut")
        )

        for horaire in horaires:
            if not horaire.traverse_minuit:
                if (
                    cls._horaire_dans_periode(horaire, today)
                    and horaire.jour_semaine == today.weekday()
                    and horaire.heure_debut <= local_time <= horaire.heure_fin
                ):
                    expiration = cls._datetime_local(today, horaire.heure_fin, moment)
                    return horaire, expiration
                continue

            # Partie du créneau située le jour de départ.
            if (
                cls._horaire_dans_periode(horaire, today)
                and horaire.jour_semaine == today.weekday()
                and local_time >= horaire.heure_debut
            ):
                expiration = cls._datetime_local(
                    today + timedelta(days=1),
                    horaire.heure_fin,
                    moment,
                )
                return horaire, expiration

            # Partie après minuit d'un créneau commencé la veille. La validité
            # de date porte sur le jour de DÉPART, pas sur le jour après minuit.
            yesterday = today - timedelta(days=1)
            if (
                cls._horaire_dans_periode(horaire, yesterday)
                and horaire.jour_semaine == yesterday.weekday()
                and local_time <= horaire.heure_fin
            ):
                expiration = cls._datetime_local(today, horaire.heure_fin, moment)
                return horaire, expiration

        return None, None

    @staticmethod
    def _horaire_dans_periode(horaire, date_reference):
        if horaire.date_debut and date_reference < horaire.date_debut:
            return False
        if horaire.date_fin and date_reference > horaire.date_fin:
            return False
        return True

    @staticmethod
    def _datetime_local(date_value, time_value, reference):
        naive = datetime.combine(date_value, time_value)
        tz = reference.tzinfo or timezone.get_current_timezone()
        return timezone.make_aware(naive, timezone=tz)

    @staticmethod
    def _normaliser_moment(moment):
        if moment is None:
            return timezone.localtime()
        if timezone.is_naive(moment):
            moment = timezone.make_aware(moment, timezone.get_current_timezone())
        return timezone.localtime(moment)

    @staticmethod
    def _point(point_vente):
        if isinstance(point_vente, PointVente):
            return point_vente
        try:
            return PointVente.objects.filter(pk=point_vente).first()
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _deny(reason, *, action, point_vente=None):
        return POSAccessDecision(
            allowed=False,
            reason=reason,
            action=action,
            point_vente_id=getattr(point_vente, "id", None),
        )

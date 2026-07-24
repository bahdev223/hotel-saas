from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal
from apps.pos.models import SessionCaisse, Vente, ShiftEmploye, AffectationPointVente, CaissePointVente
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse, MouvementCaisse, TransfertCaisse
from apps.tresorerie.services.mouvement_service import MouvementService


class RafCaisseService:

    @staticmethod
    @transaction.atomic
    def ouvrir_avec_depot(point_vente, caisse, caissier, shift, raf_employe, montant_depot):
        centrale = Caisse.objects.filter(role='CENTRALE', actif=True).first()
        if not centrale:
            raise ValueError("Aucune caisse centrale configur\u00e9e")

        montant = Decimal(str(montant_depot))
        if montant <= 0:
            raise ValueError("Le montant du d\u00e9p\u00f4t doit \u00eatre positif")
        if centrale.solde < montant:
            raise ValueError(f"Solde insuffisant en caisse centrale ({centrale.solde:,.0f} F)")

        user = raf_employe.user if raf_employe and raf_employe.user else None
        ref = f"DEP-OUV-{point_vente.code}-{timezone.now().strftime('%y%m%d%H%M%S')}"

        MouvementService.decaisser(caisse=centrale, montant=montant,
            libelle=f"[DEPOT_OUVERTURE] D\u00e9p\u00f4t ouverture {point_vente.nom}", user=user, reference=ref)
        MouvementService.encaisser(caisse=caisse, montant=montant,
            libelle=f"[DEPOT_OUVERTURE] D\u00e9p\u00f4t ouverture depuis centrale", user=user, reference=ref)

        TransfertCaisse.objects.create(
            source=centrale, destination=caisse, montant=montant, reference=ref,
            valide_par=user,
            notes=f"D\u00e9p\u00f4t d'ouverture {point_vente.nom} \u2014 RAF: {raf_employe.nom_complet}")

        session = SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').first()
        if session:
            session.solde_initial += montant
            session.save(update_fields=['solde_initial'])
            return session

        session = SessionCaisse.objects.create(
            caisse=caisse, point_vente=point_vente,
            ouverte_par=caissier,
            solde_initial=montant,
            shift=shift, statut='OUVERTE',
        )
        return session

    @staticmethod
    @transaction.atomic
    def declarer_solde_initial(session, raf_employe, nouveau_solde_initial):
        centrale = Caisse.objects.filter(role='CENTRALE', actif=True).first()
        if not centrale:
            raise ValueError("Aucune caisse centrale configur\u00e9e")

        montant = Decimal(str(nouveau_solde_initial))
        ancien = session.solde_initial
        difference = montant - ancien

        if difference == 0:
            return session

        user = raf_employe.user if raf_employe and raf_employe.user else None
        caisse = session.caisse

        if difference > 0:
            if centrale.solde < difference:
                raise ValueError(f"Solde centrale insuffisant ({centrale.solde:,.0f} F)")
            ref = f"INI-SES-{session.id}-{timezone.now().strftime('%y%m%d%H%M%S')}"
            MouvementService.decaisser(caisse=centrale, montant=difference,
                libelle=f"[SOLDE_INITIAL] Ajustement session #{session.id}", user=user, reference=ref)
            MouvementService.encaisser(caisse=caisse, montant=difference,
                libelle=f"[SOLDE_INITIAL] Ajustement session #{session.id}", user=user, reference=ref)
            TransfertCaisse.objects.create(
                source=centrale, destination=caisse, montant=difference, reference=ref,
                valide_par=user,
                notes=f"Ajustement session #{session.id} \u2014 RAF: {raf_employe.nom_complet}")
        else:
            ref = f"RET-SES-{session.id}-{timezone.now().strftime('%y%m%d%H%M%S')}"
            MouvementService.decaisser(caisse=caisse, montant=abs(difference),
                libelle=f"[SOLDE_INITIAL] Reprise session #{session.id}", user=user, reference=ref)
            MouvementService.encaisser(caisse=centrale, montant=abs(difference),
                libelle=f"[SOLDE_INITIAL] Reprise session #{session.id}", user=user, reference=ref)
            TransfertCaisse.objects.create(
                source=caisse, destination=centrale, montant=abs(difference), reference=ref,
                valide_par=user,
                notes=f"Reprise session #{session.id} \u2014 RAF: {raf_employe.nom_complet}")

        session.solde_initial = montant
        session.save(update_fields=['solde_initial'])
        return session

    @staticmethod
    @transaction.atomic
    def collecter_session(session, raf_employe, montant_transfert, notes=""):
        if session.statut != 'FERMEE':
            raise ValueError("La session n'est pas ferm\u00e9e")
        if session.statut == 'VALIDEE':
            raise ValueError("Les fonds de cette session ont d\u00e9j\u00e0 \u00e9t\u00e9 collect\u00e9s")

        montant = Decimal(str(montant_transfert))
        if montant < 0:
            raise ValueError("Le montant du transfert ne peut pas \u00eatre n\u00e9gatif")

        user = raf_employe.user if raf_employe and raf_employe.user else None
        now = timezone.now()
        caisse = session.caisse
        centrale = Caisse.objects.filter(role='CENTRALE', actif=True).first()

        transfert = None
        if montant > 0 and centrale:
            ref = f"COL-SES-{session.id}-{now.strftime('%y%m%d%H%M%S')}"
            MouvementService.decaisser(caisse=caisse, montant=montant,
                libelle=f"[COLLECTE] Collecte session #{session.id}",
                user=user, reference=ref)
            MouvementService.encaisser(caisse=centrale, montant=montant,
                libelle=f"[COLLECTE] Collecte session #{session.id}",
                user=user, reference=ref)
            transfert = TransfertCaisse.objects.create(
                source=caisse, destination=centrale, montant=montant, reference=ref,
                valide_par=user,
                notes=f"Collecte RAF {raf_employe.nom_complet} \u2014 {session.point_vente.nom if session.point_vente else ''}")

        session.validee_par = raf_employe
        session.statut = 'VALIDEE'
        session.notes = (session.notes or '') + (' | ' + notes if notes else '')
        session.save()

        if transfert:
            caisse.solde -= montant
            caisse.save()

        return {
            'session': session,
            'transfert': transfert,
        }

    @staticmethod
    def get_sessions_pour_collecte():
        sessions = SessionCaisse.objects.filter(
            statut='FERMEE'
        ).select_related(
            'point_vente', 'caisse', 'ouverte_par',
        ).order_by('point_vente__nom', 'date_ouverture')

        result = []
        for s in sessions:
            ventes = Vente.objects.filter(session_caisse=s, statut='PAYEE')
            aggs = ventes.aggregate(
                total=Sum('montant_total'), nb=Count('id'),
                especes=Sum('montant_total', filter=Q(mode_paiement='ESPECES')))
            result.append({
                'session': s,
                'total_ventes': float(aggs['total'] or 0),
                'nb_ventes': aggs['nb'] or 0,
                'total_especes': float(aggs['especes'] or 0),
                'solde_attendu': float(s.solde_initial + (aggs['total'] or 0)),
            })
        return result

    @staticmethod
    def get_sessions_en_attente():
        sessions = SessionCaisse.objects.filter(
            statut='FERMEE'
        ).select_related(
            'point_vente', 'caisse', 'ouverte_par', 'fermee_par',
        ).order_by('point_vente__nom', '-date_fermeture')

        result = []
        for s in sessions:
            ventes = Vente.objects.filter(session_caisse=s, statut='PAYEE')
            aggs = ventes.aggregate(
                total=Sum('montant_total'), nb=Count('id'),
                especes=Sum('montant_total', filter=Q(mode_paiement='ESPECES')))
            result.append({
                'session': s,
                'total_ventes': float(aggs['total'] or 0),
                'nb_ventes': aggs['nb'] or 0,
                'total_especes': float(aggs['especes'] or 0),
                'solde_attendu': float(s.solde_initial + (aggs['total'] or 0)),
                'ferme_par': s.fermee_par.nom_complet if s.fermee_par else 'N/A',
                'ferme_le': s.date_fermeture.strftime('%d/%m/%Y %H:%M') if s.date_fermeture else 'N/A',
            })
        return result

    @staticmethod
    def get_collectees():
        sessions = SessionCaisse.objects.filter(
            statut='VALIDEE'
        ).select_related(
            'point_vente', 'caisse', 'validee_par',
        ).order_by('-date_fermeture')[:50]

        result = []
        for s in sessions:
            comptage = getattr(s, 'comptage', None)
            result.append({
                'session': s,
                'collecte_par': s.validee_par.nom_complet if s.validee_par else 'N/A',
                'collecte_le': s.date_fermeture.strftime('%d/%m/%Y %H:%M') if s.date_fermeture else 'N/A',
                'montant_transfere': float(comptage.especes_comptees) if comptage else 0,
            })
        return result

    @staticmethod
    def get_demandes_ouverture():
        today = timezone.localdate()
        now = timezone.localtime()

        shifts = ShiftEmploye.objects.filter(
            debut_prevu__date=today,
        ).exclude(statut='ANNULE').select_related(
            'affectation__point_vente', 'affectation__employe',
        ).order_by('debut_prevu')

        demandes = []
        seen = set()
        for s in shifts:
            if not (s.debut_prevu <= now <= s.fin_prevue):
                continue
            pv = s.affectation.point_vente if s.affectation else None
            if not pv or pv.id in seen:
                continue
            seen.add(pv.id)
            cpv = CaissePointVente.objects.filter(point_vente=pv, actif=True).select_related('caisse').first()
            if not cpv:
                continue
            caisse = cpv.caisse
            if not SessionCaisse.objects.filter(point_vente=pv, statut='OUVERTE').exists():
                demandes.append({
                    'planning': s, 'point_vente': pv, 'caisse': caisse,
                    'employe': s.affectation.employe if s.affectation else None,
                    'solde_actuel': float(caisse.solde),
                })
        return demandes

from django.db import transaction
from django.db.models import Q, Sum, Count
from django.utils import timezone
from decimal import Decimal
from apps.pos.models import SessionCaisse, Vente
from apps.rh.models import Employe
from apps.tresorerie.models import Caisse, MouvementCaisse, TransfertCaisse
from apps.tresorerie.services.mouvement_service import MouvementService
from apps.tresorerie.services.transfert_service import TransfertService


class RafCaisseService:
    """Service des opérations caisse réservées au RAF.

    1. Dépôt d'ouverture (centrale → PV)
    2. Déclaration solde initial après ouverture
    3. Collecte différée (session déjà FERMEE par caissier → RAF collecte après)
    4. Collecte directe (RAF ferme + collecte en 1 étape)
    """

    # ─── OUVERTURE ──────────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def ouvrir_avec_depot(point_vente, caisse, caissier, planning, raf_employe, montant_depot):
        """Le RAF dépose depuis centrale → PV et ouvre la session."""
        from ..models import PointVente
        centrale = Caisse.objects.filter(role='CENTRALE', actif=True).first()
        if not centrale:
            raise ValueError("Aucune caisse centrale configurée")

        montant = Decimal(str(montant_depot))
        if montant <= 0:
            raise ValueError("Le montant du dépôt doit être positif")
        if centrale.solde < montant:
            raise ValueError(f"Solde insuffisant en caisse centrale ({centrale.solde:,.0f} F)")

        user = raf_employe.user if raf_employe and raf_employe.user else None
        ref = f"DEP-OUV-{point_vente.code}-{timezone.now().strftime('%y%m%d%H%M%S')}"

        MouvementService.decaisser(caisse=centrale, montant=montant,
            libelle=f"[DEPOT_OUVERTURE] Dépôt ouverture {point_vente.nom}", user=user, reference=ref)
        MouvementService.encaisser(caisse=caisse, montant=montant,
            libelle=f"[DEPOT_OUVERTURE] Dépôt ouverture depuis centrale", user=user, reference=ref)

        TransfertCaisse.objects.create(
            source=centrale, destination=caisse, montant=montant, reference=ref,
            valide_par=user,
            notes=f"Dépôt d'ouverture {point_vente.nom} — RAF: {raf_employe.nom_complet}")

        session = SessionCaisse.objects.filter(caisse=caisse, statut='OUVERTE').first()
        if session:
            session.solde_initial += montant
            session.ouvert_par_raf = True
            session.save(update_fields=['solde_initial', 'ouvert_par_raf'])
            return session

        session = SessionCaisse.objects.create(
            caisse=caisse, point_vente=point_vente, caissier_ouverture=caissier,
            solde_initial=montant, solde_attendu=montant,
            debut_prevu=planning.heure_debut if planning else None,
            fin_prevu=planning.heure_fin if planning else None,
            planning=planning, statut='OUVERTE', ouvert_par_raf=True)
        return session

    @staticmethod
    @transaction.atomic
    def declarer_solde_initial(session, raf_employe, nouveau_solde_initial):
        """RAF déclare/modifie le solde initial après ouverture de la session.
        Ajuste la caisse en conséquence avec un mouvement depuis la centrale."""
        centrale = Caisse.objects.filter(role='CENTRALE', actif=True).first()
        if not centrale:
            raise ValueError("Aucune caisse centrale configurée")

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
                libelle=f"[SOLDE_INITIAL] Ajustement solde initial session #{session.id}", user=user, reference=ref)
            MouvementService.encaisser(caisse=caisse, montant=difference,
                libelle=f"[SOLDE_INITIAL] Ajustement solde initial session #{session.id}", user=user, reference=ref)
            TransfertCaisse.objects.create(
                source=centrale, destination=caisse, montant=difference, reference=ref,
                valide_par=user,
                notes=f"Ajustement solde initial session #{session.id} — RAF: {raf_employe.nom_complet}")
        else:
            ref = f"RET-SES-{session.id}-{timezone.now().strftime('%y%m%d%H%M%S')}"
            MouvementService.decaisser(caisse=caisse, montant=abs(difference),
                libelle=f"[SOLDE_INITIAL] Reprise solde initial session #{session.id}", user=user, reference=ref)
            MouvementService.encaisser(caisse=centrale, montant=abs(difference),
                libelle=f"[SOLDE_INITIAL] Reprise solde initial session #{session.id}", user=user, reference=ref)
            TransfertCaisse.objects.create(
                source=caisse, destination=centrale, montant=abs(difference), reference=ref,
                valide_par=user,
                notes=f"Reprise solde initial session #{session.id} — RAF: {raf_employe.nom_complet}")

        session.solde_initial = montant
        session.solde_initial_raf = montant
        session.save(update_fields=['solde_initial', 'solde_initial_raf'])
        return session

    # ─── COLLECTE (core) ────────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def _effectuer_collecte(session, raf_employe, solde_reel, montant_transfert, notes=""):
        """Méthode centrale : transfère les fonds PV → Centrale et marque la session collectée.
        Utilisée par la collecte différée et la collecte directe."""
        montant = Decimal(str(montant_transfert))
        montant_reel = Decimal(str(solde_reel))
        reste = montant_reel - montant

        if montant < 0:
            raise ValueError("Le montant du transfert ne peut pas être négatif")
        if reste < 0:
            raise ValueError("Le transfert ne peut pas dépasser le solde réel")

        user = raf_employe.user if raf_employe and raf_employe.user else None
        now = timezone.now()
        caisse = session.caisse
        centrale = Caisse.objects.filter(role='CENTRALE', actif=True).first()

        transfert = None
        if montant > 0 and centrale:
            ref = f"COL-SES-{session.id}-{now.strftime('%y%m%d%H%M%S')}"
            MouvementService.decaisser(caisse=caisse, montant=montant,
                libelle=f"[COLLECTE] Collecte session #{session.id} — {session.point_vente.nom if session.point_vente else ''}",
                user=user, reference=ref)
            MouvementService.encaisser(caisse=centrale, montant=montant,
                libelle=f"[COLLECTE] Collecte session #{session.id} — {session.point_vente.nom if session.point_vente else ''}",
                user=user, reference=ref)
            transfert = TransfertCaisse.objects.create(
                source=caisse, destination=centrale, montant=montant, reference=ref,
                valide_par=user,
                notes=f"Collecte RAF {raf_employe.nom_complet} — {session.point_vente.nom if session.point_vente else ''}{' — ' + notes if notes else ''}")

        # Mettre à jour la session
        session.solde_reel = montant_reel
        session.depot = montant
        session.solde_restant = reste
        session.ferme_par_raf = raf_employe
        session.transfert_caisse = transfert
        session.fonds_collectes = True
        session.date_collecte = now
        session.save()

        # Solde de la caisse = solde_restant
        caisse.solde = reste
        caisse.save()

        # Écart → ajustement
        if session.difference != 0:
            MouvementCaisse.objects.create(
                caisse=caisse, type_mouvement='AJUSTEMENT',
                montant=abs(session.difference),
                libelle=f"Ajustement session #{session.id} — {'Excédent' if session.difference > 0 else 'Déficit'}",
                reference=f"ECART-SES-{session.id}", created_by=user, date=now)

        if abs(session.difference) > 5000:
            session.notes = f"Écart important: {session.difference} F. {notes}"
            session.save(update_fields=['notes'])

        return {
            'session': session, 'transfert': transfert,
            'solde_attendu': session.solde_attendu, 'solde_reel': session.solde_reel,
            'depot': session.depot, 'solde_restant': session.solde_restant,
            'difference': session.difference,
        }

    # ─── COLLECTE DIFFÉRÉE ──────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def collecter_session_fermee(session, raf_employe, solde_reel, montant_transfert, notes=""):
        """Collecte les fonds d'une session déjà fermée par le caissier.
        - solde_reel : argent physique compté par le RAF
        - montant_transfert : combien part à la centrale
        - solde_restant = solde_reel - montant_transfert (reste dans la caisse)
        """
        if session.statut != 'FERMEE':
            raise ValueError("La session n'est pas fermée")
        if session.fonds_collectes:
            raise ValueError("Les fonds de cette session ont déjà été collectés")

        session.calculer_solde_attendu()
        difference = Decimal(str(solde_reel)) - session.solde_attendu
        session.difference = difference

        return RafCaisseService._effectuer_collecte(session, raf_employe, solde_reel, montant_transfert, notes)

    # ─── COLLECTE DIRECTE ───────────────────────────────────────

    @staticmethod
    @transaction.atomic
    def collecter_et_fermer(session, raf_employe, solde_reel, montant_transfert, notes=""):
        """RAF ferme la session OUVERTE ET collecte les fonds en 1 étape."""
        if session.statut != 'OUVERTE':
            raise ValueError("La session n'est pas ouverte")

        # Calculer solde attendu + totaux par mode
        from django.db.models import Sum as SumD
        session.calculer_solde_attendu()
        ventes = Vente.objects.filter(session_caisse=session, statut='PAYEE')
        session.total_especes = ventes.filter(mode_paiement='ESPECES').aggregate(total=SumD('montant_total'))['total'] or 0
        session.total_carte = ventes.filter(mode_paiement='CARTE').aggregate(total=SumD('montant_total'))['total'] or 0
        session.total_mobile_money = ventes.filter(mode_paiement='MOBILE_MONEY').aggregate(total=SumD('montant_total'))['total'] or 0
        session.total_compte_client = ventes.filter(mode_paiement='COMPTE_CLIENT').aggregate(total=SumD('montant_total'))['total'] or 0

        session.caissier_fermeture = raf_employe
        session.date_fermeture = timezone.now()
        difference = Decimal(str(solde_reel)) - session.solde_attendu
        session.difference = difference
        session.statut = 'FERMEE'
        session.save()

        return RafCaisseService._effectuer_collecte(session, raf_employe, solde_reel, montant_transfert, notes)

    # ─── LISTES ─────────────────────────────────────────────────

    @staticmethod
    def get_sessions_pour_collecte():
        """Sessions OUVERTES (pour collecte directe)"""
        sessions = SessionCaisse.objects.filter(statut='OUVERTE').select_related(
            'point_vente', 'caisse', 'caissier_ouverture', 'planning'
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
        """Sessions FERMEE dont les fonds n'ont pas encore été collectés"""
        sessions = SessionCaisse.objects.filter(
            statut='FERMEE', fonds_collectes=False
        ).select_related(
            'point_vente', 'caisse', 'caissier_ouverture', 'caissier_fermeture', 'planning'
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
                'ferme_par': s.caissier_fermeture.nom_complet if s.caissier_fermeture else 'N/A',
                'ferme_le': s.date_fermeture.strftime('%d/%m/%Y %H:%M') if s.date_fermeture else 'N/A',
            })
        return result

    @staticmethod
    def get_collectees():
        """Sessions dont les fonds ont été collectés (historique)"""
        sessions = SessionCaisse.objects.filter(
            fonds_collectes=True
        ).select_related(
            'point_vente', 'caisse', 'ferme_par_raf', 'transfert_caisse'
        ).order_by('-date_collecte')[:50]

        result = []
        for s in sessions:
            result.append({
                'session': s,
                'collecte_par': s.ferme_par_raf.nom_complet if s.ferme_par_raf else 'N/A',
                'collecte_le': s.date_collecte.strftime('%d/%m/%Y %H:%M') if s.date_collecte else 'N/A',
                'montant_transfere': float(s.depot or 0),
                'reference_transfert': s.transfert_caisse.reference if s.transfert_caisse else 'N/A',
            })
        return result

    @staticmethod
    def get_demandes_ouverture():
        """Plannings actifs sans session ouverte où le RAF doit déposer"""
        from datetime import datetime, timedelta
        from ..models import SessionPlanning

        today = timezone.localdate()
        now = timezone.localtime()
        heure_courante = now.time()

        plannings = SessionPlanning.objects.filter(
            date=today,
        ).exclude(statut='ANNULE').select_related(
            'employe', 'point_vente', 'point_vente__caisse'
        ).order_by('heure_debut')

        demandes = []
        seen = set()
        for p in plannings:
            if p.heure_debut == p.heure_fin:
                actif = True
            elif p.heure_debut < p.heure_fin:
                actif = p.heure_debut <= heure_courante <= p.heure_fin
            else:
                actif = heure_courante >= p.heure_debut
            if not actif:
                continue
            pv = p.point_vente
            if not pv or not pv.caisse or pv.id in seen:
                continue
            seen.add(pv.id)
            if not SessionCaisse.objects.filter(point_vente=pv, statut='OUVERTE').exists():
                demandes.append({
                    'planning': p, 'point_vente': pv, 'caisse': pv.caisse,
                    'employe': p.employe, 'solde_actuel': float(pv.caisse.solde),
                })
        return demandes

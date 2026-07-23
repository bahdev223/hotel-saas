from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict


class Command(BaseCommand):
    help = "Diagnostic complet du module POS (sessions, plannings, ventes, commandes)"

    def handle(self, *args, **options):
        from apps.pos.models import SessionCaisse, SessionPlanning, Vente, Commande
        from apps.rh.models import Employe
        from django.db.models import Count, Q

        now = timezone.localtime()
        self.results = []

        def check(num, titre, ok, total, details):
            status = "OK" if ok else ("WARN" if total > 0 else "OK")
            self.results.append((num, titre, status, total, details))
            if status == "OK":
                self.stdout.write(self.style.SUCCESS(f"  [{num}] {titre} : {status} ({total})"))
            elif status == "WARN":
                self.stdout.write(self.style.WARNING(f"  [{num}] {titre} : {status} ({total})"))
                for d in details[:5]:
                    self.stdout.write(f"         {d}")
                if len(details) > 5:
                    self.stdout.write(f"         ... et {len(details)-5} autre(s)")

        self.stdout.write("=" * 60)
        self.stdout.write("POS HEALTHCHECK — Diagnostic complet")
        self.stdout.write(f"{now.strftime('%d/%m/%Y %H:%M:%S')}")
        self.stdout.write("=" * 60)

        # ─── 1. Sessions orphelines ───
        sessions = SessionCaisse.objects.filter(statut='OUVERTE').filter(
            Q(planning__isnull=True) | Q(caissier_ouverture__isnull=True) |
            Q(point_vente__isnull=True) | Q(caisse__isnull=True)
        )
        details = [f"#{s.id} plan={s.planning_id} cav={s.caissier_ouverture_id} pv={s.point_vente_id} cai={s.caisse_id}" for s in sessions]
        check(1, "Sessions orphelines (manque planning/caissier/PV/caisse)", len(details) == 0, len(details), details)

        # ─── 2. Sessions expirées (planning terminé mais encore ouverte) ───
        expirees = []
        for s in SessionCaisse.objects.filter(statut='OUVERTE', planning__isnull=False).select_related('planning'):
            p = s.planning
            if p.heure_debut == p.heure_fin:
                continue
            if p.heure_debut < p.heure_fin:
                fin = timezone.make_aware(
                    timezone.datetime.combine(p.date, p.heure_fin),
                    timezone.get_current_timezone()
                )
            else:
                fin = timezone.make_aware(
                    timezone.datetime.combine(p.date + timedelta(days=1), p.heure_fin),
                    timezone.get_current_timezone()
                )
            if now > fin:
                expirees.append(f"#{s.id} planning #{p.id} fin={p.date} {p.heure_fin}")
        check(2, "Sessions expirées (planning terminé, session ouverte)", len(expirees) == 0, len(expirees), expirees)

        # ─── 3. Doublons sur même caisse ───
        doublons = []
        par_caisse = defaultdict(list)
        for s in SessionCaisse.objects.filter(statut='OUVERTE').order_by('-date_ouverture'):
            par_caisse[s.caisse_id].append(s)
        for cid, slist in par_caisse.items():
            if len(slist) > 1:
                for s in slist[1:]:
                    doublons.append(f"caisse #{cid} : #{s.id} (ouverte avec #{slist[0].id})")
        check(3, "Doublons sur même caisse", len(doublons) == 0, len(doublons), doublons)

        # ─── 4. Ventes incohérentes (PV/caissier différent de la session) ───
        incoherentes = []
        for v in Vente.objects.filter(session_caisse__isnull=False).select_related('session_caisse').iterator():
            s = v.session_caisse
            if s.point_vente_id and v.point_vente_id and v.point_vente_id != s.point_vente_id:
                incoherentes.append(f"vente #{v.id} PV={v.point_vente_id} != session #{s.id} PV={s.point_vente_id}")
            elif v.caissier_id and s.caissier_ouverture_id and v.caissier_id != s.caissier_ouverture_id:
                incoherentes.append(f"vente #{v.id} caissier={v.caissier_id} != session #{s.id} caissier={s.caissier_ouverture_id}")
        check(4, "Ventes incoherentes (PV/caissier != session)", len(incoherentes) == 0, len(incoherentes), incoherentes)

        # ─── 5. Sessions très anciennes (≥48h) ───
        anciennes = []
        seuil_48h = now - timedelta(hours=48)
        for s in SessionCaisse.objects.filter(statut='OUVERTE', date_ouverture__isnull=False):
            if s.date_ouverture < seuil_48h:
                anciennes.append(f"#{s.id} ouverte depuis {s.date_ouverture.strftime('%d/%m/%Y %H:%M')}")
        check(5, "Sessions tres anciennes (+48h)", len(anciennes) == 0, len(anciennes), anciennes)

        # ─── 6. Ventes après fermeture de session ───
        apres_fermeture = []
        for v in Vente.objects.filter(session_caisse__isnull=False, session_caisse__date_fermeture__isnull=False).select_related('session_caisse').iterator():
            s = v.session_caisse
            if v.created_at and s.date_fermeture and v.created_at > s.date_fermeture:
                apres_fermeture.append(
                    f"vente #{v.id} le {v.created_at.strftime('%d/%m/%Y %H:%M')} après fermeture session #{s.id} le {s.date_fermeture.strftime('%d/%m/%Y %H:%M')}"
                )
        check(6, "Ventes après fermeture session", len(apres_fermeture) == 0, len(apres_fermeture), apres_fermeture)

        # ─── 7. Sessions ouvertes sans aucun mouvement ───
        sans_mvt = []
        for s in SessionCaisse.objects.filter(statut='OUVERTE').annotate(
            nb_ventes=Count('ventes'),
        ):
            if s.nb_ventes == 0:
                sans_mvt.append(f"#{s.id} caisse #{s.caisse_id} ouverte depuis {s.date_ouverture.strftime('%d/%m/%Y %H:%M') if s.date_ouverture else '?'}")
        check(7, "Sessions ouvertes sans aucun mouvement", len(sans_mvt) == 0, len(sans_mvt), sans_mvt)

        # ─── 8. Plannings sans employé ou employé supprimé ───
        plannings_orphelins = []
        for p in SessionPlanning.objects.filter(employe__isnull=True).select_related('point_vente'):
            plannings_orphelins.append(f"planning #{p.id} PV={p.point_vente} date={p.date} (employe_id=NULL)")
        check(8, "Plannings sans employé", len(plannings_orphelins) == 0, len(plannings_orphelins), plannings_orphelins)

        # ─── 9. Chevauchement de plannings (même employé, même date) ───
        chevauchements = []
        from itertools import combinations
        plannings_par_emp_date = defaultdict(list)
        for p in SessionPlanning.objects.exclude(statut='ANNULE').values('employe_id', 'date', 'id', 'heure_debut', 'heure_fin'):
            if p['employe_id'] and p['date']:
                plannings_par_emp_date[(p['employe_id'], p['date'])].append(p)
        for (eid, date), plist in plannings_par_emp_date.items():
            for a, b in combinations(plist, 2):
                if a['heure_debut'] < b['heure_fin'] and b['heure_debut'] < a['heure_fin']:
                    chevauchements.append(f"employé #{eid} le {date} : #{a['id']} ({a['heure_debut']}-{a['heure_fin']}) chevauche #{b['id']} ({b['heure_debut']}-{b['heure_fin']})")
        check(9, "Chevauchement plannings (même employé/même date)", len(chevauchements) == 0, len(chevauchements), chevauchements)

        # ─── 10. Employés actifs sans point_vente ───
        sans_pv = list(Employe.objects.filter(actif=True, point_vente__isnull=True).values_list('id', 'nom', 'prenom'))
        details10 = [f"#{e[0]} {e[1]} {e[2]}" for e in sans_pv]
        check(10, "Employés actifs sans point de vente", False, len(sans_pv), details10)

        # ─── Bilan ───
        self.stdout.write("=" * 60)
        ok_count = sum(1 for r in self.results if r[2] == "OK")
        warn_count = sum(1 for r in self.results if r[2] == "WARN")
        self.stdout.write(f"OK   : {ok_count}/10")
        if warn_count:
            self.stdout.write(self.style.WARNING(f"WARN : {warn_count}/10"))
        else:
            self.stdout.write(self.style.SUCCESS("WARN : 0/10"))
        severity = "TOUT OK" if warn_count == 0 else "ANOMALIES DETECTEES"
        self.stdout.write(f"> {severity}")
        self.stdout.write("=" * 60)

        if warn_count:
            self.stdout.write(self.style.WARNING("Prochaines étapes suggérées :"))
            self.stdout.write("  - Inspecter les WARN ci-dessus avec le shell Django")
            self.stdout.write("  - Lancer python manage.py verifier_sessions --fix pour corriger")
            self.stdout.write("  - Vérifier les plannings via l'interface admin")

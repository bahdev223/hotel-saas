from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from collections import defaultdict


class Command(BaseCommand):
    help = "Diagnostic complet du module POS (sessions, shifts, ventes, commandes)"

    def handle(self, *args, **options):
        from apps.pos.models import SessionCaisse, ShiftEmploye, Vente, Commande, AffectationPointVente
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
        self.stdout.write("POS HEALTHCHECK \u2014 Diagnostic complet")
        self.stdout.write(f"{now.strftime('%d/%m/%Y %H:%M:%S')}")
        self.stdout.write("=" * 60)

        # 1. Sessions orphelines
        sessions = SessionCaisse.objects.filter(statut='OUVERTE').filter(
            Q(ouverte_par__isnull=True) | Q(point_vente__isnull=True) | Q(caisse__isnull=True)
        )
        details = [f"#{s.id} cav={s.ouverte_par_id} pv={s.point_vente_id} cai={s.caisse_id}" for s in sessions]
        check(1, "Sessions orphelines (manque caissier/PV/caisse)", len(details) == 0, len(details), details)

        # 2. Doublons sur même caisse
        doublons = []
        par_caisse = defaultdict(list)
        for s in SessionCaisse.objects.filter(statut='OUVERTE').order_by('-date_ouverture'):
            par_caisse[s.caisse_id].append(s)
        for cid, slist in par_caisse.items():
            if len(slist) > 1:
                for s in slist[1:]:
                    doublons.append(f"caisse #{cid} : #{s.id} (ouverte avec #{slist[0].id})")
        check(2, "Doublons sur m\u00eame caisse", len(doublons) == 0, len(doublons), doublons)

        # 3. Ventes incohérentes
        incoherentes = []
        for v in Vente.objects.filter(session_caisse__isnull=False).select_related('session_caisse').iterator():
            s = v.session_caisse
            if s.point_vente_id and v.point_vente_id and v.point_vente_id != s.point_vente_id:
                incoherentes.append(f"vente #{v.id} PV={v.point_vente_id} != session #{s.id} PV={s.point_vente_id}")
            elif v.caissier_id and s.ouverte_par_id and v.caissier_id != s.ouverte_par_id:
                incoherentes.append(f"vente #{v.id} caissier={v.caissier_id} != session #{s.id} caissier={s.ouverte_par_id}")
        check(3, "Ventes incoh\u00e9rentes (PV/caissier != session)", len(incoherentes) == 0, len(incoherentes), incoherentes)

        # 4. Sessions très anciennes (≥48h)
        anciennes = []
        seuil_48h = now - timedelta(hours=48)
        for s in SessionCaisse.objects.filter(statut='OUVERTE', date_ouverture__isnull=False):
            if s.date_ouverture < seuil_48h:
                anciennes.append(f"#{s.id} ouverte depuis {s.date_ouverture.strftime('%d/%m/%Y %H:%M')}")
        check(4, "Sessions tres anciennes (+48h)", len(anciennes) == 0, len(anciennes), anciennes)

        # 5. Ventes après fermeture de session
        apres_fermeture = []
        for v in Vente.objects.filter(session_caisse__isnull=False, session_caisse__date_fermeture__isnull=False).select_related('session_caisse').iterator():
            if v.created_at and v.session_caisse.date_fermeture and v.created_at > v.session_caisse.date_fermeture:
                apres_fermeture.append(
                    f"vente #{v.id} le {v.created_at.strftime('%d/%m/%Y %H:%M')} apr\u00e8s fermeture session #{v.session_caisse.id} le {v.session_caisse.date_fermeture.strftime('%d/%m/%Y %H:%M')}"
                )
        check(5, "Ventes apr\u00e8s fermeture session", len(apres_fermeture) == 0, len(apres_fermeture), apres_fermeture)

        # 6. Sessions ouvertes sans aucun mouvement
        sans_mvt = []
        for s in SessionCaisse.objects.filter(statut='OUVERTE').annotate(nb_ventes=Count('ventes')):
            if s.nb_ventes == 0:
                sans_mvt.append(f"#{s.id} caisse #{s.caisse_id} ouverte depuis {s.date_ouverture.strftime('%d/%m/%Y %H:%M') if s.date_ouverture else '?'}")
        check(6, "Sessions ouvertes sans aucun mouvement", len(sans_mvt) == 0, len(sans_mvt), sans_mvt)

        # 7. Employés actifs sans affectation PV
        affectes = AffectationPointVente.objects.filter(actif=True).values_list('employe_id', flat=True).distinct()
        sans_pv = list(Employe.objects.filter(actif=True).exclude(id__in=affectes).values_list('id', 'nom', 'prenom'))
        details7 = [f"#{e[0]} {e[1]} {e[2]}" for e in sans_pv]
        check(7, "Employ\u00e9s actifs sans affectation point de vente", False, len(sans_pv), details7)

        # Bilan
        self.stdout.write("=" * 60)
        ok_count = sum(1 for r in self.results if r[2] == "OK")
        warn_count = sum(1 for r in self.results if r[2] == "WARN")
        self.stdout.write(f"OK   : {ok_count}/7")
        if warn_count:
            self.stdout.write(self.style.WARNING(f"WARN : {warn_count}/7"))
        else:
            self.stdout.write(self.style.SUCCESS("WARN : 0/7"))
        severity = "TOUT OK" if warn_count == 0 else "ANOMALIES D\u00c9TECT\u00c9ES"
        self.stdout.write(f"> {severity}")
        self.stdout.write("=" * 60)

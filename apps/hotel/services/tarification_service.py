from decimal import Decimal
from datetime import date, timedelta
from django.db import transaction, models
from django.utils import timezone

from ..models.tarifs import TarifChambre, PlanTarifaire, TypeTarif
from ..models.types_chambres import TypeChambre


class TarificationService:
    @classmethod
    def trouver_tarifs(
        cls,
        *,
        type_chambre,
        date_debut=None,
        date_fin=None,
        plan_tarifaire=None,
        type_tarif=None,
    ):
        qs = TarifChambre.objects.select_related(
            "plan_tarifaire", "type_tarif", "type_chambre"
        ).filter(
            type_chambre=type_chambre,
            actif=True,
            plan_tarifaire__actif=True,
            type_tarif__actif=True,
        )

        if plan_tarifaire:
            qs = qs.filter(plan_tarifaire=plan_tarifaire)
        if type_tarif:
            qs = qs.filter(type_tarif=type_tarif)

        if date_debut:
            qs = qs.filter(
                models.Q(date_debut__isnull=True) | models.Q(date_debut__lte=date_debut)
            )
        if date_fin:
            qs = qs.filter(
                models.Q(date_fin__isnull=True) | models.Q(date_fin__gte=date_fin)
            )

        return qs.order_by("plan_tarifaire__priorite", "type_tarif__ordre")

    @classmethod
    def trouver_tarif_optimal(
        cls,
        *,
        type_chambre,
        date_debut,
        date_fin=None,
        client=None,
        duree_heures=None,
    ):
        tarifs = cls.trouver_tarifs(type_chambre=type_chambre, date_debut=date_debut)

        plan_prioritaire = None
        if client:
            plan_prioritaire = cls._determiner_plan_client(client)

        if plan_prioritaire:
            plan_tarif = tarifs.filter(plan_tarifaire=plan_prioritaire).first()
            if plan_tarif:
                return plan_tarif

        return tarifs.order_by("plan_tarifaire__priorite", "type_tarif__ordre").first()

    @classmethod
    def calculer_montant(cls, *, tarif, date_debut, date_fin, nombre_adultes=1, nombre_enfants=0):
        if tarif.type_tarif.unite_facturation == TypeTarif.UniteFacturation.NUITEE:
            nuits = (date_fin.date() - date_debut.date()).days
            if nuits < 1:
                nuits = 1
            montant_base = tarif.montant * Decimal(str(nuits))
        elif tarif.type_tarif.unite_facturation == TypeTarif.UniteFacturation.HEURE:
            heures = max(1, int((date_fin - date_debut).total_seconds() / 3600))
            montant_base = tarif.montant * Decimal(str(heures))
        elif tarif.type_tarif.unite_facturation == TypeTarif.UniteFacturation.JOURNEE:
            jours = max(1, (date_fin.date() - date_debut.date()).days)
            montant_base = tarif.montant * Decimal(str(jours))
        elif tarif.type_tarif.unite_facturation == TypeTarif.UniteFacturation.DEMI_JOURNEE:
            montant_base = tarif.montant
        elif tarif.type_tarif.unite_facturation == TypeTarif.UniteFacturation.FORFAIT:
            montant_base = tarif.montant
        else:
            montant_base = tarif.montant

        supplements = Decimal("0")
        if nombre_adultes > tarif.nombre_personnes_incluses:
            adultes_sup = nombre_adultes - tarif.nombre_personnes_incluses
            supplements += tarif.supplement_adulte * Decimal(str(adultes_sup))

        if nombre_enfants > 0:
            supplements += tarif.supplement_enfant * Decimal(str(nombre_enfants))

        return montant_base + supplements

    @classmethod
    def _determiner_plan_client(cls, client):
        if client.type_client == "ENTREPRISE":
            return PlanTarifaire.objects.filter(
                type_client=PlanTarifaire.TypeClient.ENTREPRISE,
                actif=True,
            ).order_by("priorite").first()
        elif client.type_client == "AGENCE":
            return PlanTarifaire.objects.filter(
                type_client=PlanTarifaire.TypeClient.AGENCE,
                actif=True,
            ).order_by("priorite").first()
        return None

    @classmethod
    def appliquer_tarif(cls, *, reservation, chambre, tarif, quantite, utilisateur):
        return {
            "tarif_source": tarif,
            "type_tarif_nom": tarif.type_tarif.nom,
            "plan_tarifaire_nom": tarif.plan_tarifaire.nom,
            "montant_unitaire": tarif.montant,
            "quantite": quantite,
            "montant_total": tarif.montant * Decimal(str(quantite)),
        }

    @classmethod
    def tarifs_par_type_chambre(cls, etablissement):
        from django.db import models
        return (
            TarifChambre.objects.select_related(
                "type_chambre", "plan_tarifaire", "type_tarif"
            )
            .filter(
                etablissement=etablissement,
                actif=True,
                plan_tarifaire__actif=True,
                type_tarif__actif=True,
            )
            .order_by("type_chambre__ordre", "plan_tarifaire__priorite", "type_tarif__ordre")
        )

    @classmethod
    def resumer_grille(cls, etablissement):
        tarifs = cls.tarifs_par_type_chambre(etablissement)
        grille = {}
        for t in tarifs:
            key = str(t.type_chambre)
            if key not in grille:
                grille[key] = []
            grille[key].append(t)
        return grille

from decimal import Decimal
from apps.stocks.constants import NatureMouvement
from apps.stocks.models import Valorisation, MouvementStock, Article, Depot


class ValorisationService:

    @staticmethod
    def calculer_stock_valorise(article, depot=None):
        if depot:
            valorisations = Valorisation.objects.filter(article=article, depot=depot)
        else:
            valorisations = Valorisation.objects.filter(article=article)

        result = {
            "quantite_totale": Decimal("0"),
            "valeur_totale": Decimal("0"),
            "depots": [],
        }
        for v in valorisations:
            result["quantite_totale"] += v.quantite_totale
            result["valeur_totale"] += v.valeur_totale
            result["depots"].append({
                "depot": v.depot.code,
                "methode": v.methode,
                "cout_unitaire_moyen": v.cout_unitaire_moyen,
                "quantite": v.quantite_totale,
                "valeur": v.valeur_totale,
            })

        return result

    @staticmethod
    def recalculer_pmp(article, depot):
        mouvements = MouvementStock.objects.filter(
            article=article,
            depot=depot,
            valide=True,
            nature=NatureMouvement.ENTREE,
            prix_unitaire__isnull=False,
        ).order_by("date_mouvement")

        quantite_totale = Decimal("0")
        valeur_totale = Decimal("0")

        for mvt in mouvements:
            qte = abs(mvt.quantite)
            quantite_totale += qte
            valeur_totale += qte * mvt.prix_unitaire

        if quantite_totale > 0:
            pmp = valeur_totale / quantite_totale
        else:
            pmp = Decimal("0")

        Valorisation.objects.update_or_create(
            article=article,
            depot=depot,
            defaults={
                "methode": "PMP",
                "cout_unitaire_moyen": pmp,
                "quantite_totale": quantite_totale,
                "valeur_totale": valeur_totale,
            },
        )
        return pmp

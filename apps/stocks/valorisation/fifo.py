from decimal import Decimal
from django.utils import timezone
from apps.stocks.models import CoucheValorisation


class FIFOStrategy:
    """Premier entrÃ©, premier sorti.

    Chaque entrÃ©e crÃ©e une couche (CoucheValorisation) avec sa quantitÃ© et
    son prix. Les sorties consomment les couches les plus anciennes d'abord.
    """

    method_code = "FIFO"
    method_name = "Premier entrÃ©, premier sorti"

    @classmethod
    def enregistrer_entree(cls, valorisation, quantite, prix_unitaire, mouvement=None):
        couche = CoucheValorisation.objects.create(
            article=valorisation.article,
            depot=valorisation.depot,
            quantite_restante=quantite,
            prix_unitaire=prix_unitaire,
            date_entree=mouvement.date_mouvement if mouvement else timezone.now(),
            mouvement=mouvement,
        )
        valorisation.quantite_totale += quantite
        valorisation.cout_unitaire_moyen = cls.get_cout_unitaire(valorisation)
        valorisation.valeur_totale = cls.get_valeur_totale(valorisation)
        valorisation.save(update_fields=["cout_unitaire_moyen", "quantite_totale", "valeur_totale"])
        return couche

    @classmethod
    def enregistrer_sortie(cls, valorisation, quantite, mouvement=None):
        qte_restante = abs(Decimal(quantite))
        cout_total = Decimal("0")
        couches = CoucheValorisation.objects.filter(
            article=valorisation.article,
            depot=valorisation.depot,
            quantite_restante__gt=0,
        ).order_by("date_entree", "id")

        for couche in couches:
            if qte_restante <= 0:
                break
            a_consommer = min(qte_restante, couche.quantite_restante)
            cout_total += a_consommer * couche.prix_unitaire
            couche.quantite_restante -= a_consommer
            couche.save(update_fields=["quantite_restante"])
            qte_restante -= a_consommer
            valorisation.quantite_totale -= a_consommer

        if qte_restante > 0:
            valorisation.quantite_totale -= qte_restante
            cout_total += qte_restante * cls.get_cout_unitaire(valorisation)

        valorisation.cout_unitaire_moyen = cls.get_cout_unitaire(valorisation)
        valorisation.valeur_totale = cls.get_valeur_totale(valorisation)
        valorisation.save(update_fields=["cout_unitaire_moyen", "quantite_totale", "valeur_totale"])
        return cout_total

    @classmethod
    def get_cout_unitaire(cls, valorisation):
        couches = CoucheValorisation.objects.filter(
            article=valorisation.article,
            depot=valorisation.depot,
            quantite_restante__gt=0,
        )
        total_qte = sum((c.quantite_restante for c in couches), Decimal("0"))
        if not total_qte:
            return Decimal("0")
        total_valeur = sum(
            (c.quantite_restante * c.prix_unitaire for c in couches),
            Decimal("0"),
        )
        return total_valeur / total_qte

    @classmethod
    def get_valeur_totale(cls, valorisation):
        couches = CoucheValorisation.objects.filter(
            article=valorisation.article,
            depot=valorisation.depot,
            quantite_restante__gt=0,
        )
        return sum(
            (c.quantite_restante * c.prix_unitaire for c in couches),
            Decimal("0"),
        )

    @classmethod
    def initialiser(cls, valorisation, quantite, prix_unitaire):
        CoucheValorisation.objects.create(
            article=valorisation.article,
            depot=valorisation.depot,
            quantite_restante=quantite,
            prix_unitaire=prix_unitaire,
            date_entree=timezone.now(),
        )
        valorisation.quantite_totale = quantite
        valorisation.cout_unitaire_moyen = prix_unitaire
        valorisation.valeur_totale = quantite * prix_unitaire
        valorisation.save(update_fields=["cout_unitaire_moyen", "quantite_totale", "valeur_totale"])

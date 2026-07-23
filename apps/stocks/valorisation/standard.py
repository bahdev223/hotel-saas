from decimal import Decimal


class StandardCostStrategy:
    """CoÃ»t standard â€” le prix unitaire est fixe, donnÃ© Ã  l'initialisation.

    Les entrÃ©es et sorties n'affectent pas le coÃ»t unitaire. Utile pour les
    articles dont le prix est administrÃ© (ex: prix de cession interne).
    """

    method_code = "STANDARD"
    method_name = "CoÃ»t standard"

    @classmethod
    def enregistrer_entree(cls, valorisation, quantite, prix_unitaire, mouvement=None):
        valorisation.quantite_totale += quantite
        valorisation.valeur_totale = cls.get_valeur_totale(valorisation)
        valorisation.save(update_fields=["quantite_totale", "valeur_totale"])

    @classmethod
    def enregistrer_sortie(cls, valorisation, quantite, mouvement=None):
        qte = abs(Decimal(quantite))
        if qte > valorisation.quantite_totale:
            qte = valorisation.quantite_totale
        cout = qte * valorisation.cout_unitaire_moyen
        valorisation.quantite_totale -= qte
        valorisation.valeur_totale = cls.get_valeur_totale(valorisation)
        valorisation.save(update_fields=["quantite_totale", "valeur_totale"])
        return cout

    @classmethod
    def get_cout_unitaire(cls, valorisation):
        return valorisation.cout_unitaire_moyen

    @classmethod
    def get_valeur_totale(cls, valorisation):
        return valorisation.quantite_totale * valorisation.cout_unitaire_moyen

    @classmethod
    def initialiser(cls, valorisation, quantite, prix_unitaire):
        valorisation.cout_unitaire_moyen = prix_unitaire
        valorisation.quantite_totale = quantite
        valorisation.valeur_totale = quantite * prix_unitaire
        valorisation.save(update_fields=["cout_unitaire_moyen", "quantite_totale", "valeur_totale"])

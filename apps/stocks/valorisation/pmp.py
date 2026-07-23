from decimal import Decimal


class PMPStrategy:
    """Prix Moyen PondÃ©rÃ© â€” la valeur est la moyenne pondÃ©rÃ©e de tous les achats."""

    method_code = "PMP"
    method_name = "Prix Moyen PondÃ©rÃ©"

    @classmethod
    def enregistrer_entree(cls, valorisation, quantite, prix_unitaire, mouvement=None):
        ancienne_valeur = valorisation.quantite_totale * valorisation.cout_unitaire_moyen
        nouvelle_valeur = quantite * prix_unitaire
        nouvelle_quantite = valorisation.quantite_totale + quantite
        if nouvelle_quantite > 0:
            valorisation.cout_unitaire_moyen = (
                ancienne_valeur + nouvelle_valeur
            ) / nouvelle_quantite
        valorisation.quantite_totale = nouvelle_quantite
        valorisation.valeur_totale = valorisation.quantite_totale * valorisation.cout_unitaire_moyen
        valorisation.save(update_fields=["cout_unitaire_moyen", "quantite_totale", "valeur_totale"])
        return valorisation.cout_unitaire_moyen

    @classmethod
    def enregistrer_sortie(cls, valorisation, quantite, mouvement=None):
        qte = abs(Decimal(quantite))
        if qte > valorisation.quantite_totale:
            qte = valorisation.quantite_totale
        cout = qte * valorisation.cout_unitaire_moyen
        valorisation.quantite_totale -= qte
        valorisation.valeur_totale = valorisation.quantite_totale * valorisation.cout_unitaire_moyen
        valorisation.save(update_fields=["quantite_totale", "valeur_totale"])
        return cout

    @classmethod
    def get_cout_unitaire(cls, valorisation):
        return valorisation.cout_unitaire_moyen

    @classmethod
    def get_valeur_totale(cls, valorisation):
        return valorisation.valeur_totale

    @classmethod
    def initialiser(cls, valorisation, quantite, prix_unitaire):
        valorisation.cout_unitaire_moyen = prix_unitaire
        valorisation.quantite_totale = quantite
        valorisation.valeur_totale = quantite * prix_unitaire
        valorisation.save(update_fields=["cout_unitaire_moyen", "quantite_totale", "valeur_totale"])

class BaseValuationStrategy:
    """Classe de base pour une stratÃ©gie de valorisation.

    Chaque stratÃ©gie concrÃ¨te dÃ©finit comment les entrÃ©es et sorties
    affectent la valeur du stock, sans que le moteur de stock ait besoin
    de connaÃ®tre la mÃ©thode utilisÃ©e.
    """

    method_code = None
    method_name = ""

    @classmethod
    def enregistrer_entree(cls, valorisation, quantite, prix_unitaire, mouvement=None):
        raise NotImplementedError

    @classmethod
    def enregistrer_sortie(cls, valorisation, quantite, mouvement=None):
        raise NotImplementedError

    @classmethod
    def get_cout_unitaire(cls, valorisation):
        raise NotImplementedError

    @classmethod
    def get_valeur_totale(cls, valorisation):
        raise NotImplementedError

    @classmethod
    def initialiser(cls, valorisation, quantite, prix_unitaire):
        raise NotImplementedError

from decimal import Decimal
from django.core.exceptions import ValidationError
from apps.stock.models import ConversionUnite, Conditionnement

class ConversionUniteService:
    """Service de conversion entre les unités et conditionnements"""

    @classmethod
    def convertir(cls, quantite, unite_source, unite_dest, produit=None):
        """
        Convertit une quantité d'une unité à une autre.
        1. Identique -> Retourne quantite
        2. Via Conditionnement (si produit fourni et correspond)
        3. Via ConversionUnite (générique)
        """
        quantite = Decimal(str(quantite))
        
        if unite_source == unite_dest:
            return quantite

        # 1. Vérifier si c'est une conversion liée à un conditionnement du produit (Ex: Caisse -> Pièce)
        if produit:
            # Source = Conditionnement, Dest = Unité de base
            cond_source = Conditionnement.objects.filter(
                produit=produit, nom=unite_source.nom, unite_destination=unite_dest
            ).first()
            if cond_source:
                return quantite * cond_source.facteur
                
            # Source = Unité de base, Dest = Conditionnement
            cond_dest = Conditionnement.objects.filter(
                produit=produit, nom=unite_dest.nom, unite_destination=unite_source
            ).first()
            if cond_dest:
                return quantite / cond_dest.facteur

        # 2. Chercher une conversion générique directe (ex: Kg -> g)
        conversion = ConversionUnite.objects.filter(
            unite_source=unite_source,
            unite_dest=unite_dest
        ).first()
        if conversion:
            return quantite * conversion.facteur

        # 3. Chercher une conversion générique inverse (ex: g -> Kg)
        conversion_inv = ConversionUnite.objects.filter(
            unite_source=unite_dest,
            unite_dest=unite_source
        ).first()
        if conversion_inv:
            return quantite / conversion_inv.facteur

        # 4. Échec
        raise ValidationError(
            f"Impossible de convertir {quantite} {unite_source.symbole} en {unite_dest.symbole}. "
            "Aucune règle de conversion ou de conditionnement trouvée."
        )

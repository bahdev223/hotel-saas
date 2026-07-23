# apps/stock/services/transfert_service.py
from decimal import Decimal
from django.db import transaction
from ..models import Produit, Entrepot
from .mouvement_service import MouvementStockService


class TransfertService:
    """Service de gestion des transferts entre entrepôts — délègue les mutations à MouvementStockService"""
    
    @classmethod
    @transaction.atomic
    def transfert_entre_entrepots(cls, produit_id, quantite, entrepot_source_id, entrepot_dest_id, 
                                    utilisateur, reference=None, notes=None, sous_unite_id=None):
        
        produit = Produit.objects.get(id=produit_id)
        source = Entrepot.objects.get(id=entrepot_source_id)
        dest = Entrepot.objects.get(id=entrepot_dest_id)

        if source.id == dest.id:
            raise ValueError("L'entrepôt source et destination sont identiques")

        quantite_saisie = Decimal(str(quantite))
        
        quantite_reelle = quantite_saisie
        unite_texte = produit.unite_base
        conversion_texte = ""
        
        if sous_unite_id:
            try:
                sous_unite = produit.sous_unites.get(id=sous_unite_id, actif=True)
                quantite_reelle = quantite_saisie * Decimal(str(sous_unite.facteur))
                unite_texte = f"{quantite_saisie} {sous_unite.nom}"
                conversion_texte = f"{quantite_saisie} {sous_unite.nom} = {quantite_reelle} {produit.unite_base}"
            except Exception as e:
                raise Exception(f"Erreur conversion sous-unité: {e}")
        
        # Sortie de la source via le moteur unique
        MouvementStockService.sortie_stock(
            produit=produit, entrepot=source,
            quantite=quantite_reelle, utilisateur=utilisateur,
            motif='reapprovisionnement', valeur_unitaire=produit.prix_achat or Decimal('0'),
            reference=reference,
            raison=f"Transfert vers {dest.nom}",
            entrepot_dest=dest,
        )
        
        # Entrée dans la destination via le moteur unique
        raison_complete = f"Transfert depuis {source.nom}: {conversion_texte}" if conversion_texte else f"Transfert depuis {source.nom}"
        
        mouvement = MouvementStockService.entree_stock(
            produit=produit, entrepot=dest,
            quantite=quantite_reelle, utilisateur=utilisateur,
            motif='reapprovisionnement', valeur_unitaire=produit.prix_achat or Decimal('0'),
            reference=reference,
            raison=raison_complete,
            unite_texte=unite_texte,
            entrepot_source=source,
        )
        
        return mouvement
    
    @classmethod
    def transfert_central_vers_bar(cls, produit_id, quantite, utilisateur, 
                                    reference=None, notes=None, sous_unite_id=None):
        """Transfert du stock central vers le bar (avec ou sans sous-unitÃ©)"""
        try:
            central = Entrepot.objects.get(type_entrepot='CENTRAL', actif=True)
        except Entrepot.DoesNotExist:
            central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
            if not central:
                raise Exception("EntrepÃ´t CENTRAL non trouvÃ©")
        
        try:
            bar = Entrepot.objects.get(type_entrepot='BAR', actif=True)
        except Entrepot.DoesNotExist:
            bar = Entrepot.objects.filter(type_entrepot='BAR').first()
            if not bar:
                bar = Entrepot.objects.create(
                    code='BAR001',
                    nom='BAR',
                    type_entrepot='BAR',
                    actif=True
                )
        
        return cls.transfert_entre_entrepots(
            produit_id=produit_id,
            quantite=quantite,
            entrepot_source_id=central.id,
            entrepot_dest_id=bar.id,
            utilisateur=utilisateur,
            reference=reference,
            notes=notes,
            sous_unite_id=sous_unite_id
        )
    
    @classmethod
    def transfert_central_vers_restaurant(cls, produit_id, quantite, utilisateur,
                                           reference=None, notes=None, sous_unite_id=None):
        """Transfert du stock central vers le restaurant (avec ou sans sous-unitÃ©)"""
        try:
            central = Entrepot.objects.get(type_entrepot='CENTRAL', actif=True)
        except Entrepot.DoesNotExist:
            central = Entrepot.objects.filter(type_entrepot='CENTRAL').first()
            if not central:
                raise Exception("EntrepÃ´t CENTRAL non trouvÃ©")
        
        try:
            resto = Entrepot.objects.get(type_entrepot='RESTAURANT', actif=True)
        except Entrepot.DoesNotExist:
            resto = Entrepot.objects.filter(type_entrepot='RESTAURANT').first()
            if not resto:
                resto = Entrepot.objects.create(
                    code='RST001',
                    nom='RESTAURANT',
                    type_entrepot='RESTAURANT',
                    actif=True
                )
        
        return cls.transfert_entre_entrepots(
            produit_id=produit_id,
            quantite=quantite,
            entrepot_source_id=central.id,
            entrepot_dest_id=resto.id,
            utilisateur=utilisateur,
            reference=reference,
            notes=notes,
            sous_unite_id=sous_unite_id
        )
    
    @classmethod
    def get_stock_entrepot(cls, code_entrepot, produit_id=None):
        """Récupère le stock d'un entrepôt"""
        try:
            entrepot = Entrepot.objects.get(code=code_entrepot)
        except Entrepot.DoesNotExist:
            entrepot = Entrepot.objects.filter(type_entrepot=code_entrepot).first()
            if not entrepot:
                raise Exception(f"Entrepôt {code_entrepot} non trouvé")
        
        stocks = StockEntrepot.objects.filter(entrepot=entrepot).select_related('produit')
        
        if produit_id:
            stocks = stocks.filter(produit_id=produit_id)
        
        return stocks

    @classmethod
    @transaction.atomic
    def annuler_transfert(cls, mouvement, user):
        """Annule un transfert (SORTIE + ENTREE inversées) — réservé RAF."""
        from ..models.mouvement_stock import MouvementStock
        from django.contrib.contenttypes.models import ContentType

        if mouvement.type_mouvement != 'ENTREE' or mouvement.motif != 'reapprovisionnement':
            raise ValueError("Seul un transfert (ENTREE + réappro) peut être annulé")

        # Trouver la SORTIE correspondante
        sortie = MouvementStock.objects.filter(
            produit=mouvement.produit,
            quantite=mouvement.quantite,
            type_mouvement='SORTIE',
            motif='reapprovisionnement',
            reference=mouvement.reference,
        ).first()
        if not sortie:
            raise ValueError("Mouvement de sortie correspondant introuvable")

        # Inverser : entrée dans la source, sortie de la destination
        MouvementStockService.entree_stock(
            produit=mouvement.produit, entrepot=sortie.entrepot,
            quantite=mouvement.quantite, utilisateur=user,
            motif='reprise', valeur_unitaire=mouvement.valeur_unitaire or Decimal('0'),
            reference=f"ANNUL-{mouvement.reference}" if mouvement.reference else None,
            raison=f"Annulation transfert depuis {mouvement.entrepot.nom}",
        )
        MouvementStockService.sortie_stock(
            produit=mouvement.produit, entrepot=mouvement.entrepot,
            quantite=mouvement.quantite, utilisateur=user,
            motif='reprise', valeur_unitaire=mouvement.valeur_unitaire or Decimal('0'),
            reference=f"ANNUL-{mouvement.reference}" if mouvement.reference else None,
            raison=f"Annulation transfert vers {sortie.entrepot.nom}",
        )

        return mouvement
    
    


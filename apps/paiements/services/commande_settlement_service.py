from decimal import Decimal
import uuid
from django.db import transaction
from django.utils import timezone


class CommandeSettlementError(ValueError):
    pass


class CommandeSettlementService:
    """
    Service unique et obligatoire pour régler une commande restaurant.

    Parcours :
      1. Verrouiller la commande (select_for_update)
      2. Vérifier qu'elle n'est pas déjà réglée
      3. Vérifier qu'une session caisse est ouverte
      4. Créer le Paiement (VALID)
      5. Créer la Vente + Lignes (avec snapshots coût/marge)
      6. Consommer le stock (échec → annule tout)
      7. Mouvement de caisse
      8. Comptabilité (échec → IntegrationError, ne bloque pas)
      9. Retourner le résultat structuré
    """

    @classmethod
    @transaction.atomic
    def regler(
        cls,
        *,
        commande,
        montant=None,
        mode_paiement='ESPECES',
        caisse=None,
        utilisateur,
        notes='',
    ):
        from apps.pos.models import Commande
        from apps.paiements.models import Paiement
        from apps.tresorerie.services.mouvement_service import MouvementService
        from apps.restaurant.services.consumption_service import RestaurantConsumptionService

        # 1. Verrouiller la commande
        commande = Commande.objects.select_for_update().get(pk=commande.pk)

        # 2. Vérifier qu'elle n'est pas déjà réglée
        if commande.statut == 'PAYEE' or commande.vente_id:
            raise CommandeSettlementError(
                f"Commande #{commande.numero} déjà réglée"
            )

        if commande.statut == 'ANNULEE':
            raise CommandeSettlementError(
                f"Commande #{commande.numero} annulée — impossible de régler"
            )

        # CREDIT interdit pour les clients passagers
        if mode_paiement == 'CREDIT':
            from apps.clients.models import Client
            if not commande.client or commande.client_id == Client.PASSAGER_ID:
                raise CommandeSettlementError(
                    "Le mode Crédit nécessite un client enregistré"
                )

        _montant = montant if montant is not None else commande.montant_total
        _montant = Decimal(str(_montant))
        if _montant <= 0:
            raise CommandeSettlementError("Le montant doit être supérieur à 0")

        # 3. Caisse : automatique depuis le point de vente
        pv = commande.point_vente
        from apps.tresorerie.models import Caisse as CaisseModel
        _caisse = caisse or CaisseModel.objects.filter(point_vente=pv, actif=True).first()
        if not _caisse:
            raise CommandeSettlementError(
                f"Aucune caisse active configurée sur le point de vente {pv}"
            )
        _caisse = CaisseModel.objects.select_for_update().get(pk=_caisse.pk)

        # 4. Session obligatoire
        from apps.pos.services.caisse_session_service import get_session_active_pv
        session = get_session_active_pv(pv)
        if not session:
            from apps.paiements.services.paiement_engine import SessionRequiseError
            raise SessionRequiseError(
                f"Aucune session de caisse ouverte sur {pv.nom} "
                f"— ouvrez une session pour encaisser."
            )

        # 5. Résoudre l'employé
        employe = getattr(commande, 'created_by', None)
        if not employe:
            from apps.rh.models import Employe
            employe = Employe.objects.filter(user=utilisateur).first()

        # 6. Créer le Paiement (directement VALIDE)
        from django.contrib.contenttypes.models import ContentType
        paiement = Paiement.objects.create(
            type_paiement='VENTE',
            montant=_montant,
            sens='ENTREE',
            mode=mode_paiement,
            caisse=_caisse,
            content_type=ContentType.objects.get_for_model(commande),
            object_id=str(commande.id),
            client=commande.client,
            created_by=utilisateur,
            valide_par=utilisateur,
            date_validation=timezone.now(),
            statut='VALIDE',
            notes=notes,
        )

        # 7. Mouvement de caisse (sauf CREDIT/SOLDE)
        if mode_paiement not in ('CREDIT', 'SOLDE'):
            MouvementService.encaisser(
                caisse=_caisse,
                montant=_montant,
                libelle=f"Règlement commande {commande.numero}",
                user=utilisateur,
                reference=commande.numero,
                source=paiement,
            )

        # 8. Créer la Vente + LigneVente (avec snapshots coût/marge)
        from apps.pos.models import Vente, LigneVente
        vente = Vente.objects.create(
            point_vente=pv,
            caisse=_caisse,
            session_caisse=session,
            numero=f"V{uuid.uuid4().hex[:8].upper()}",
            client_nom=commande.client_nom,
            mode_paiement=mode_paiement,
            montant_total=_montant,
            caissier=employe,
            encaisse_par=employe,
            statut='PAYEE',
        )

        cout_revient_total = Decimal('0')
        marge_totale = Decimal('0')

        for ligne in commande.lignes.all():
            cout_unitaire = cls._calculer_cout_ligne(ligne)
            marge = (ligne.prix_unitaire - cout_unitaire) * ligne.quantite
            cout_revient_total += cout_unitaire * ligne.quantite
            marge_totale += marge

            LigneVente.objects.create(
                vente=vente,
                produit=ligne.produit,
                menu=ligne.menu,
                quantite=ligne.quantite,
                prix_unitaire=ligne.prix_unitaire,
                cout_revient=cout_unitaire,
                marge=marge,
                notes=ligne.notes,
            )

        vente.cout_revient_total = cout_revient_total
        vente.marge_totale = marge_totale
        vente.save(update_fields=['cout_revient_total', 'marge_totale'])

        # 9. Lier la vente à la commande
        commande.vente = vente
        commande.statut = 'PAYEE'
        commande.save(update_fields=['vente', 'statut'])

        # 10. Consommer le stock (ÉCHEC = ANNULATION TOTALE)
        RestaurantConsumptionService.consommer_commande(
            commande=commande,
            entrepot=commande.entrepot or pv.entrepot,
            utilisateur=utilisateur.username if hasattr(utilisateur, 'username') else str(utilisateur),
        )

        # 11. Comptabilité (échec enregistré, ne bloque pas le règlement)
        try:
            from apps.pos.services.vente_compta_service import VenteComptaService
            VenteComptaService.generer_ecriture_vente(vente, utilisateur)
        except Exception as exc:
            cls._enregistrer_erreur_integration(
                module='VENTE',
                operation='COMPTABILISATION',
                objet=vente,
                message=f"Erreur écriture comptable vente #{vente.numero}",
                erreur=exc,
            )

        # 12. Facture
        try:
            from apps.facturation.services import FactureGenerators
            facture = FactureGenerators.depuis_commande(commande)
            facture.emettre()
            facture.marquer_payee()
        except Exception as exc:
            cls._enregistrer_erreur_integration(
                module='FACTURATION',
                operation='EMISSION',
                objet=vente,
                message=f"Erreur création facture vente #{vente.numero}",
                erreur=exc,
            )

        return {
            'commande': commande,
            'vente': vente,
            'paiement': paiement,
            'montant': _montant,
            'mode': mode_paiement,
        }

    @classmethod
    def _calculer_cout_ligne(cls, ligne):
        """Calcule le coût unitaire d'une ligne de commande (produit, menu ou recette)."""
        if ligne.produit:
            return Decimal(str(ligne.produit.prix_achat or 0))
        if ligne.menu:
            return cls._calculer_cout_menu_reel(ligne)
        if ligne.recette:
            return ligne.recette.cout_unitaire_rendement()
        return Decimal('0')

    @classmethod
    def _calculer_cout_menu_reel(cls, ligne):
        """
        Coût réel d'une ligne menu basé sur les choix enregistrés + fixes.
        Utilise les snapshots si disponibles.
        """
        cout = Decimal('0')
        if not ligne.menu:
            return cout

        for ligne_menu in ligne.menu.lignes.filter(type_ligne='FIXE'):
            if ligne_menu.recette:
                cout += ligne_menu.recette.cout_unitaire_rendement() * Decimal(str(ligne_menu.quantite))

        for choix in ligne.choix_menu.select_related('recette'):
            if choix.cout_unitaire_snapshot and choix.cout_unitaire_snapshot > 0:
                cout_choix = choix.cout_unitaire_snapshot
            elif choix.recette:
                cout_choix = choix.recette.cout_unitaire_rendement()
            else:
                cout_choix = Decimal('0')
            cout += cout_choix * Decimal(str(choix.quantite))

        return cout

    @classmethod
    def _enregistrer_erreur_integration(cls, module, operation, objet, message, erreur):
        """Enregistre une erreur d'intégration sans bloquer le flux principal."""
        try:
            from django.contrib.contenttypes.models import ContentType
            from apps.core.models import IntegrationError

            IntegrationError.objects.create(
                module=module,
                operation=operation,
                content_type=ContentType.objects.get_for_model(objet) if objet else None,
                object_id=str(objet.pk) if objet else None,
                message=message,
                details=str(erreur),
                traceback=__import__('traceback', fromlist=['format_exc']).format_exc(),
                status='OPEN',
            )
        except Exception:
            pass

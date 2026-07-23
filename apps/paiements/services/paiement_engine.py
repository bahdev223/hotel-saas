import uuid
from decimal import Decimal
from django.db import transaction, models
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from apps.paiements.models import Paiement
from apps.tresorerie.services.mouvement_service import MouvementService
from apps.comptabilite.services import EcritureComptableService


class SessionRequiseError(ValueError):
    """Levée quand un encaissement de commande est tenté sans session de caisse ouverte."""
    pass


class PaiementEngine:

    @staticmethod
    @transaction.atomic
    def encaisser(data, user):
        """
        Encaissement centralisé.

        data = {
            'mode': 'ESPECES|CARTE|MOBILE_MONEY|VIREMENT|CHEQUE',
            'montant': Decimal,
            'caisse_id': int,
            'type_paiement': 'VENTE|ACHAT|...',
            # Source : une ou plusieurs des options suivantes
            'facture_id': str,        # Facultatif
            'commande_id': int,        # Facultatif
            'client_id': str,          # Facultatif (dépôt client)
            # Métadonnées
            'notes': '',
            'reference_externe': '',
        }

        Retourne le Paiement créé et validé.
        """
        montant = Decimal(str(data['montant']))
        mode = data['mode']
        caisse_id = data['caisse_id']
        notes = data.get('notes', '')
        ref_ext = data.get('reference_externe', '')
        type_paiement = data.get('type_paiement', 'VENTE')

        if montant <= 0:
            raise ValueError("Le montant doit être supérieur à 0")

        # Résoudre l'objet source
        objet, source_label = PaiementEngine._resoudre_source(data)

        # Commande POS : caisse du point de vente (automatique) + session ouverte obligatoire
        from apps.pos.models import Commande
        if isinstance(objet, Commande):
            pv = objet.point_vente
            if not pv or not pv.caisse_id:
                raise ValueError(f"Caisse non configurée sur le point de vente de la commande {objet.numero}")
            caisse_id = pv.caisse_id
            from apps.pos.services.caisse_session_service import get_session_ouverte_pv
            if not get_session_ouverte_pv(pv):
                raise SessionRequiseError(
                    f"Aucune session de caisse ouverte sur {pv.nom} — ouvrez une session pour encaisser."
                )

        from apps.tresorerie.models import Caisse
        caisse = Caisse.objects.select_for_update().get(id=caisse_id)

        # Router MOBILE_MONEY vers le compte mobile dédié
        if mode == 'MOBILE_MONEY' and caisse.type_financier != 'MOBILE_MONEY':
            mm_caisse = Caisse.objects.filter(type_financier='MOBILE_MONEY', actif=True).first()
            if mm_caisse:
                caisse = mm_caisse

        # Résoudre le client pour lier au Paiement
        from apps.clients.models import Client
        client_paiement = None
        client_id_data = data.get('client_id')
        if client_id_data:
            client_paiement = Client.objects.filter(id=client_id_data).first()
        elif isinstance(objet, Client):
            client_paiement = objet
        elif hasattr(objet, 'client') and objet.client:
            client_paiement = objet.client

        # Créer le Paiement (directement VALIDE)
        paiement = Paiement.objects.create(
            type_paiement=type_paiement,
            montant=montant,
            sens='ENTREE',
            mode=mode,
            caisse=caisse,
            content_type=ContentType.objects.get_for_model(objet) if objet else None,
            object_id=str(objet.id) if objet else None,
            client=client_paiement,
            created_by=user,
            valide_par=user,
            date_validation=timezone.now(),
            statut='VALIDE',
            notes=notes,
            reference_externe=ref_ext,
        )

        # Pour CREDIT et SOLDE : pas de mouvement de trésorerie, on crée/modifie le CompteClient
        if mode in ('CREDIT', 'SOLDE'):
            from apps.comptabilite.models import CompteClient, ExerciceModel
            from datetime import date

            client = client_paiement
            if client:
                exercice = ExerciceModel.objects.filter(
                    date_debut__lte=date.today(),
                    date_fin__gte=date.today(),
                    cloture=False
                ).first()
                if not exercice:
                    exercice = ExerciceModel.objects.filter(cloture=False).first()
                if exercice:
                    compte, _ = CompteClient.objects.select_for_update().get_or_create(
                        client=client, exercice=exercice
                    )
                    # Vérifier le plafond de crédit
                    if mode == 'CREDIT' and client.credit_plafond > 0:
                        dette_actuelle = abs(compte.solde) if compte.solde < 0 else 0
                        if dette_actuelle + montant > client.credit_plafond:
                            raise ValueError(
                                f"Plafond de crédit dépassé ({dette_actuelle:,.0f} + {montant:,.0f} > {client.credit_plafond:,.0f} F)"
                            )
                    compte.solde -= montant  # Débit : dette (CREDIT) ou utilisation solde (SOLDE)
                    compte.save()
        else:
            MouvementService.encaisser(
                caisse=caisse,
                montant=montant,
                libelle=f"Paiement {paiement.reference} - {source_label}",
                user=user,
                reference=paiement.reference,
                source=paiement,
            )

            try:
                from apps.clients.models import Client
                if isinstance(objet, Client):
                    EcritureComptableService.creer_ecriture_depot_client(
                        caisse=caisse, montant=montant,
                        libelle=source_label,
                        tiers_client=objet, user=user,
                    )
                elif objet:
                    EcritureComptableService.creer_ecriture_paiement_client(
                        caisse=caisse, montant=montant,
                        libelle=source_label,
                        tiers_client=objet, user=user,
                    )
            except Exception:
                import traceback
                traceback.print_exc()

        # Mise à jour de l'objet source
        PaiementEngine._update_source(objet, data, montant, paiement)

        return paiement

    @staticmethod
    def _resoudre_source(data):
        """Retourne (objet, label) selon ce qui est fourni."""
        if data.get('facture_id'):
            from apps.facturation.models import FactureModel
            obj = FactureModel.objects.get(id=data['facture_id'])
            return obj, f"Facture {obj.numero}"
        if data.get('commande_id'):
            from apps.pos.models import Commande
            obj = Commande.objects.get(id=data['commande_id'])
            return obj, f"Commande #{obj.id}"
        if data.get('client_id'):
            from apps.clients.models import Client
            obj = Client.objects.get(id=data['client_id'])
            return obj, f"Dépôt client {obj.nom}"
        return None, "Paiement direct"

    @staticmethod
    def _update_source(objet, data, montant, paiement=None):
        """Met à jour l'objet source après paiement."""
        if objet is None:
            return

        # Si c'est une facture : marquer payée si solde atteint
        from apps.facturation.models import FactureModel
        if isinstance(objet, FactureModel):
            if objet.reste_a_payer <= 0:
                objet.marquer_payee()

        # Si c'est une commande : créer la Vente + déduire le stock + mettre à jour le statut
        from apps.pos.models import Commande, Vente, LigneVente
        if isinstance(objet, Commande):
            if not objet.vente and paiement:
                # Session du PV de la commande — garantie ouverte par le verrou dans encaisser()
                from apps.pos.services.caisse_session_service import get_session_ouverte_pv
                session = get_session_ouverte_pv(objet.point_vente)

                vente = Vente.objects.create(
                    point_vente=objet.point_vente,
                    caisse=paiement.caisse,
                    session_caisse=session,
                    numero=f"V{uuid.uuid4().hex[:8].upper()}",
                    client_nom=objet.client_nom,
                    mode_paiement=data.get('mode', 'ESPECES'),
                    montant_total=montant,
                    caissier=objet.created_by,
                    encaisse_par=objet.created_by,
                    statut='PAYEE',
                )
                for ligne in objet.lignes.all():
                    LigneVente.objects.create(
                        vente=vente, produit=ligne.produit, menu=ligne.menu,
                        quantite=ligne.quantite, prix_unitaire=ligne.prix_unitaire, notes=ligne.notes
                    )
                objet.vente = vente
                objet.statut = 'PAYEE'
                objet.save()
                # Déduire le stock de l'entrepôt choisi à la commande
                from apps.pos.services.pos_service import deduire_stock_commande
                deduire_stock_commande(objet, objet.entrepot_id)
            if hasattr(objet, 'facture') and objet.facture:
                if objet.facture.reste_a_payer <= 0:
                    objet.facture.marquer_payee()

        # Si c'est un client (dépôt) : mettre à jour CompteClient
        from apps.clients.models import Client
        if isinstance(objet, Client):
            from datetime import date
            from decimal import Decimal
            from apps.comptabilite.models import CompteClient, ExerciceModel
            exercice = ExerciceModel.objects.filter(
                date_debut__lte=date.today(),
                date_fin__gte=date.today(),
                cloture=False
            ).first()
            if not exercice:
                exercice = ExerciceModel.objects.filter(cloture=False).first()
            if exercice:
                compte, _ = CompteClient.objects.select_for_update().get_or_create(
                    client=objet, exercice=exercice
                )
                compte.solde += Decimal(str(montant))
                compte.save()

    @staticmethod
    def get_factures_impayees(filtres=None):
        """Retourne les factures impayées avec filtres optionnels."""
        from apps.facturation.models import FactureModel
        from django.db.models import Q

        qs = FactureModel.objects.filter(
            Q(statut='EMISE') | (Q(statut='BROUILLON') & Q(lignes__isnull=False))
        ).distinct()

        if filtres:
            if filtres.get('search'):
                qs = qs.filter(
                    Q(numero__icontains=filtres['search']) |
                    Q(client_nom__icontains=filtres['search'])
                )
            if filtres.get('client_id'):
                from apps.clients.models import Client
                try:
                    client = Client.objects.get(id=filtres['client_id'])
                    qs = qs.filter(client_nom__icontains=client.nom)
                except Client.DoesNotExist:
                    pass

        result = []
        for f in qs:
            reste = f.reste_a_payer
            if reste > 0:
                result.append({
                    'id': f.id,
                    'numero': f.numero,
                    'client_nom': f.client_nom,
                    'montant_total': float(f.montant_total),
                    'total_paye': float(f.total_paye),
                    'reste_a_payer': float(reste),
                    'date': f.date_emission.isoformat() if f.date_emission else None,
                    'type': 'facture',
                })
        return result

    @staticmethod
    def get_commandes_impayees(filtres=None):
        """Retourne les commandes avec facture impayée."""
        from apps.pos.models import Commande
        from apps.facturation.models import FactureModel
        from django.db.models import Q

        qs = Commande.objects.filter(
            facture__isnull=False
        ).exclude(
            facture__statut='PAYEE'
        ).select_related('facture', 'client')

        if filtres:
            if filtres.get('search'):
                qs = qs.filter(
                    Q(id__icontains=filtres['search']) |
                    Q(client__nom__icontains=filtres['search']) |
                    Q(facture__numero__icontains=filtres['search'])
                )
            if filtres.get('point_vente_id'):
                qs = qs.filter(point_vente_id=filtres['point_vente_id'])

        result = []
        for c in qs:
            reste = c.facture.reste_a_payer
            if reste > 0:
                result.append({
                    'id': c.id,
                    'numero': f"CMD-{c.id}",
                    'facture_numero': c.facture.numero,
                    'client_nom': c.client.nom if c.client else 'Anonyme',
                    'montant_total': float(c.facture.montant_total),
                    'total_paye': float(c.facture.total_paye),
                    'reste_a_payer': float(reste),
                    'date': c.created_at.isoformat() if c.created_at else None,
                    'type': 'commande',
                    'point_vente': c.point_vente.nom if c.point_vente else '',
                })
        return result

    @staticmethod
    def get_solde_client(client_id):
        """Calcule le solde client à partir de CompteClient (inclut dettes CREDIT et dépôts)."""
        from apps.clients.models import Client
        from apps.comptabilite.models import CompteClient, ExerciceModel
        from datetime import date

        client = Client.objects.get(id=client_id)

        exercice = ExerciceModel.objects.filter(
            date_debut__lte=date.today(),
            date_fin__gte=date.today(),
            cloture=False
        ).first()
        if not exercice:
            exercice = ExerciceModel.objects.filter(cloture=False).first()

        solde = 0
        if exercice:
            compte = CompteClient.objects.filter(
                client=client, exercice=exercice
            ).first()
            if compte:
                solde = float(compte.solde)

        return {
            'client_id': client.id,
            'nom': client.nom,
            'solde': solde,
        }

    @staticmethod
    def get_caisses_disponibles(user):
        """Retourne les caisses accessibles à l'utilisateur."""
        from apps.tresorerie.models import Caisse

        qs = Caisse.objects.filter(actif=True)

        # Si l'utilisateur est lié à un point de vente, filtrer
        if hasattr(user, 'point_vente_associe') and user.point_vente_associe:
            pv = user.point_vente_associe
            if pv.caisse:
                qs = qs.filter(id=pv.caisse.id)

        # Si employé avec rôle CAISSIER, ne montrer que sa caisse
        if hasattr(user, 'employe'):
            roles = user.groups.values_list('name', flat=True)
            if 'CAISSIER' in roles and not ('COMPTABLE' in roles or 'PATRON' in roles or 'MANAGER' in roles):
                if hasattr(user, 'point_vente_associe') and user.point_vente_associe and user.point_vente_associe.caisse:
                    qs = qs.filter(id=user.point_vente_associe.caisse.id)

        return [{'id': c.id, 'code': c.code, 'nom': c.nom, 'solde': float(c.solde)} for c in qs]

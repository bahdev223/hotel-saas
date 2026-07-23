# apps/comptabilite/services/ecriture_comptable.py
from decimal import Decimal
from datetime import date, datetime
from django.db import transaction
from ..models import EcritureModel, LigneEcritureModel, JournalModel, CompteModel, ExerciceModel


class EcritureComptableService:
    """Service central de creation d'ecritures comptables - point d'entree unique"""

    # ─── Helpers ───────────────────────────────────────────────

    @classmethod
    def _get_exercice(cls, date_operation=None):
        if not date_operation:
            date_operation = date.today()
        exercice = ExerciceModel.objects.filter(
            date_debut__lte=date_operation,
            date_fin__gte=date_operation,
            cloture=False
        ).first()
        if not exercice:
            exercice = ExerciceModel.objects.filter(cloture=False).first()
        return exercice

    @classmethod
    def _get_or_create_journal(cls, code, libelle, type_journal):
        journal, _ = JournalModel.objects.get_or_create(
            code=code,
            defaults={'libelle': libelle, 'type_journal': type_journal, 'actif': True}
        )
        return journal

    @classmethod
    def _get_compte(cls, code_or_id):
        if code_or_id is None:
            return None
        if isinstance(code_or_id, int):
            return CompteModel.objects.filter(id=code_or_id, actif=True).first()
        compte = CompteModel.objects.filter(code=code_or_id, actif=True).first()
        if compte is not None:
            return compte
        if isinstance(code_or_id, str) and code_or_id.isdigit():
            return CompteModel.objects.filter(id=int(code_or_id), actif=True).first()
        return None

    @classmethod
    def _get_compte_caisse(cls, caisse):
        if caisse and caisse.compte_comptable:
            return caisse.compte_comptable
        if caisse:
            mapping = {'ESPECES': '571', 'BANQUE': '521', 'MOBILE_MONEY': '581'}
            code = mapping.get(caisse.type_financier, '571')
            return cls._get_compte(code)
        return cls._get_compte('571')

    @classmethod
    def _generer_reference(cls, prefix, dt=None, seq=None):
        if not dt:
            dt = datetime.now()
        if seq:
            return f"{prefix}-{dt.strftime('%Y%m%d')}-{seq}"
        return f"{prefix}-{dt.strftime('%Y%m%d%H%M%S')}"

    @classmethod
    def _creer_ecriture(cls, reference, date_ecriture, libelle, journal, lignes,
                        exercice=None, piece=None, validee=True, user=None):
        if not exercice:
            exercice = cls._get_exercice(date_ecriture)

        ecriture = EcritureModel.objects.create(
            reference=reference,
            date_ecriture=date_ecriture,
            libelle=libelle,
            journal=journal,
            piece=piece,
            exercice=exercice,
            validee=validee,
            created_by=user.username if hasattr(user, 'username') and user else str(user or '')
        )

        for ligne in lignes:
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=ligne['compte'],
                debit=ligne.get('debit', 0),
                credit=ligne.get('credit', 0),
                libelle=ligne.get('libelle', libelle),
                tiers=ligne.get('tiers')
            )

        return ecriture

    # ─── Operations sur les ventes ────────────────────────────

    @classmethod
    @transaction.atomic
    def creer_ecriture_vente(cls, caisse, montant, libelle, compte_produit_code, user=None):
        """Debit: Caisse (57x) / Credit: Compte de produit (70x)"""
        journal = cls._get_or_create_journal('VN', 'Ventes', 'VENTES')
        compte_caisse = cls._get_compte_caisse(caisse)
        compte_produit = cls._get_compte(compte_produit_code)
        ref = cls._generer_reference('VN')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': compte_caisse, 'debit': montant, 'libelle': f"Encaissement vente"},
            {'compte': compte_produit, 'credit': montant, 'libelle': libelle},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_facture_vente(cls, montant_ttc, montant_tva, libelle,
                                     compte_client, compte_produit, compte_tva=None, user=None):
        """Debit: Client (411) / Credit: Produit (70x) + TVA (443)"""
        journal = cls._get_or_create_journal('VN', 'Ventes', 'VENTES')
        cc = cls._get_compte(compte_client)
        cp = cls._get_compte(compte_produit)
        ref = cls._generer_reference('FV')
        lignes = [
            {'compte': cc, 'debit': montant_ttc, 'libelle': libelle},
            {'compte': cp, 'credit': montant_ttc - montant_tva, 'libelle': libelle},
        ]
        if montant_tva > 0 and compte_tva:
            lignes.append({'compte': cls._get_compte(compte_tva), 'credit': montant_tva, 'libelle': f"TVA {libelle}"})
        return cls._creer_ecriture(ref, date.today(), libelle, journal, lignes, user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_paiement_client(cls, caisse, montant, libelle, tiers_client, user=None):
        """Debit: Caisse (57x) / Credit: Client (411)"""
        journal = cls._get_or_create_journal('TR', 'Trésorerie', 'TRESORERIE')
        compte_caisse = cls._get_compte_caisse(caisse)
        ref = cls._generer_reference('EN')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': compte_caisse, 'debit': montant, 'libelle': f"Encaissement {libelle}"},
            {'compte': tiers_client.compte if hasattr(tiers_client, 'compte') else cls._get_compte('411'),
             'credit': montant, 'libelle': libelle, 'tiers': tiers_client},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_depot_client(cls, caisse, montant, libelle, tiers_client, user=None):
        """Debit: Caisse (57x) / Credit: Avances clients (419)"""
        journal = cls._get_or_create_journal('TR', 'Trésorerie', 'TRESORERIE')
        compte_caisse = cls._get_compte_caisse(caisse)
        ref = cls._generer_reference('AC')
        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': compte_caisse, 'debit': montant},
            {'compte': cls._get_compte('419'), 'credit': montant, 'tiers': tiers_client},
        ], user=user)

    # ─── Operations sur les achats / fournisseurs ──────────────

    @classmethod
    @transaction.atomic
    def creer_ecriture_achat(cls, montant_ttc, montant_tva, montant_ht, libelle,
                             compte_charge, compte_fournisseur, compte_tva=None, user=None):
        """Debit: Charge (6x) + TVA / Credit: Fournisseur (401)"""
        journal = cls._get_or_create_journal('AC', 'Achats', 'ACHATS')
        cch = cls._get_compte(compte_charge)
        cf = cls._get_compte(compte_fournisseur)
        ref = cls._generer_reference('AC')
        lignes = [
            {'compte': cch, 'debit': montant_ht, 'libelle': libelle},
            {'compte': cf, 'credit': montant_ttc, 'libelle': libelle},
        ]
        if montant_tva > 0 and compte_tva:
            lignes.append({'compte': cls._get_compte(compte_tva), 'debit': montant_tva, 'libelle': f"TVA {libelle}"})
        return cls._creer_ecriture(ref, date.today(), libelle, journal, lignes, user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_charge(cls, caisse, montant, libelle, compte_charge,
                              beneficiaire=None, date_operation=None, user=None):
        """Debit: Charge (6x) / Credit: Caisse (57x)"""
        if not date_operation:
            date_operation = date.today()
        journal = cls._determiner_journal_paiement(caisse)
        compte_caisse = cls._get_compte_caisse(caisse)
        cc = cls._get_compte(compte_charge) or cls._get_compte('658')
        ref = cls._generer_reference('CH', date_operation)

        lignes = [
            {'compte': cc, 'debit': montant, 'libelle': libelle},
            {'compte': compte_caisse, 'credit': montant, 'libelle': f"Paiement {libelle}"},
        ]
        if beneficiaire:
            libelle = f"{libelle} - {beneficiaire}"

        return cls._creer_ecriture(ref, date_operation, libelle, journal, lignes,
                                   piece=f"DEP-{date_operation.strftime('%Y%m%d')}", user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_paiement_fournisseur(cls, caisse, montant, libelle, tiers_fournisseur, user=None):
        """Debit: Fournisseur (401) / Credit: Caisse (57x)"""
        journal = cls._determiner_journal_paiement(caisse)
        compte_caisse = cls._get_compte_caisse(caisse)
        ref = cls._generer_reference('PF')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte('401'), 'debit': montant, 'libelle': libelle, 'tiers': tiers_fournisseur},
            {'compte': compte_caisse, 'credit': montant, 'libelle': f"Paiement fournisseur"},
        ], user=user)

    # ─── Operations de tresorerie ──────────────────────────────

    @classmethod
    def _determiner_journal_paiement(cls, caisse):
        if not caisse:
            return cls._get_or_create_journal('OD', 'Operations Diverses', 'OD')
        if caisse.est_banque:
            return cls._get_or_create_journal('BQ', 'Banque', 'BANQUE')
        return cls._get_or_create_journal('CS', 'Caisse', 'CAISSE')

    @classmethod
    @transaction.atomic
    def creer_ecriture_transfert(cls, caisse_source, caisse_dest, montant, libelle, user=None):
        """Debit: Caisse destination / Credit: Caisse source"""
        journal = cls._get_or_create_journal('TR', 'Transferts', 'CAISSE')
        ref = cls._generer_reference('TRF')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte_caisse(caisse_dest), 'debit': montant,
             'libelle': f"Transfert vers {caisse_dest.nom}"},
            {'compte': cls._get_compte_caisse(caisse_source), 'credit': montant,
             'libelle': f"Transfert depuis {caisse_source.nom}"},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_depot_banque(cls, caisse, montant, libelle, user=None):
        """Debit: Banque (521) / Credit: Caisse source (57x)"""
        journal = cls._get_or_create_journal('BQ', 'Banque', 'BANQUE')
        ref = cls._generer_reference('DB')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte('521'), 'debit': montant, 'libelle': f"Depot banque"},
            {'compte': cls._get_compte_caisse(caisse), 'credit': montant,
             'libelle': f"Depot depuis {caisse.nom}"},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_retrait_banque(cls, caisse, montant, libelle, user=None):
        """Retrait banque: Debit Caisse (571) / Credit Banque (521)"""
        journal = cls._get_or_create_journal('BQ', 'Banque', 'BANQUE')
        ref = cls._generer_reference('RB')
        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte_caisse(caisse), 'debit': montant,
             'libelle': f"Retrait banque vers {caisse.nom}"},
            {'compte': cls._get_compte('521'), 'credit': montant, 'libelle': f"Retrait banque"},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_remboursement_client(cls, caisse, montant, libelle, tiers_client, user=None):
        """Remboursement depot client: Debit 419 / Credit 571"""
        journal = cls._get_or_create_journal('CS', 'Caisse', 'CAISSE')
        ref = cls._generer_reference('REM')
        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte('419'), 'debit': montant,
             'libelle': libelle, 'tiers': tiers_client},
            {'compte': cls._get_compte_caisse(caisse), 'credit': montant,
             'libelle': f"Remboursement client"},
        ], user=user)

    # ─── Operations de cloture / session POS ───────────────────

    @classmethod
    @transaction.atomic
    def creer_ecriture_cloture_session(cls, session, total_ventes, depot, ecart, user=None):
        """Regroupe les ventes d'une session POS en une ecriture globale
           Debit: Caisse (57x) du montant attendu
           Credit: Produit (70x) — total ventes
           + ecart eventuel en charge/produit
        """
        journal = cls._get_or_create_journal('CS', 'Cloture Sessions', 'CAISSE')
        point_vente = session.point_vente
        caisse = point_vente.caisse if point_vente else None
        compte_caisse = cls._get_compte_caisse(caisse)
        libelle = f"Cloture session {session.code} - {session.date_ouverture}"
        ref = cls._generer_reference('CL', session.date_ouverture or date.today())
        montant_attendu = total_ventes

        lignes = [
            {'compte': compte_caisse, 'debit': montant_attendu,
             'libelle': f"Ventes session {session.code}"},
        ]

        produit_par_defaut = cls._get_compte('706')
        lignes.append({
            'compte': produit_par_defaut, 'credit': montant_attendu,
            'libelle': f"Ventes {point_vente.nom if point_vente else ''}" if total_ventes else libelle,
        })

        if ecart > 0:
            if depot >= montant_attendu:
                compte_ecart = cls._get_compte('658')
            else:
                compte_ecart = cls._get_compte('758')
            lignes.append({
                'compte': compte_ecart,
                'debit': ecart if ecart > 0 else 0,
                'credit': -ecart if ecart < 0 else 0,
                'libelle': f"Ecart de caisse session {session.code}"
            })

        return cls._creer_ecriture(ref, session.date_ouverture or date.today(), libelle, journal,
                                   lignes, user=user)

    # ─── Operations RH (salaires) ──────────────────────────────

    @classmethod
    @transaction.atomic
    def creer_ecriture_salaire(cls, montant_brut, montant_net, montant_cnps, montant_impot,
                               montant_avances, libelle, caisse=None, user=None):
        """Debit: Charge personnel (661) du brut
           Credit: Caisse (57x) du net
           Credit: Etat (447) impot
           Credit: Organismes sociaux (431) CNPS
           Debit: Avances (425) si avances deduites
        """
        journal = cls._get_or_create_journal('PA', 'Paie', 'CAISSE')
        compte_caisse = cls._get_compte_caisse(caisse) if caisse else cls._get_compte('571')
        ref = cls._generer_reference('PAIE')

        lignes = [
            {'compte': cls._get_compte('661'), 'debit': montant_brut, 'libelle': libelle},
            {'compte': compte_caisse, 'credit': montant_net, 'libelle': f"Net a payer"},
        ]
        if montant_cnps > 0:
            lignes.append({'compte': cls._get_compte('431'), 'credit': montant_cnps, 'libelle': 'CNPS'})
        if montant_impot > 0:
            lignes.append({'compte': cls._get_compte('447'), 'credit': montant_impot, 'libelle': 'IRPP'})
        if montant_avances > 0:
            lignes.append({'compte': cls._get_compte('425'), 'debit': montant_avances, 'libelle': 'Avances deduites'})

        return cls._creer_ecriture(ref, date.today(), libelle, journal, lignes, user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_paiement_salaire(cls, caisse, montant, libelle, user=None):
        """Paiement effectif des salaires: Debit 421 / Credit Caisse"""
        journal = cls._determiner_journal_paiement(caisse)
        compte_caisse = cls._get_compte_caisse(caisse)
        ref = cls._generer_reference('PS')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte('421'), 'debit': montant, 'libelle': libelle},
            {'compte': compte_caisse, 'credit': montant, 'libelle': f"Paiement salaires"},
        ], user=user)

    # ─── Operations de stock ───────────────────────────────────

    @classmethod
    @transaction.atomic
    def creer_ecriture_entree_stock(cls, montant, libelle, compte_stock='31', compte_variation='6031', user=None):
        """Entree en stock: Debit Stock (3x) / Credit Variation stock (603)"""
        journal = cls._get_or_create_journal('ST', 'Stock', 'ACHATS')
        ref = cls._generer_reference('ES')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte(compte_stock), 'debit': montant, 'libelle': libelle},
            {'compte': cls._get_compte(compte_variation), 'credit': montant, 'libelle': libelle},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_sortie_stock(cls, montant, libelle, compte_charge='6032', compte_stock='31', user=None):
        """Sortie de stock: Debit Charge (603) / Credit Stock (3x)"""
        journal = cls._get_or_create_journal('ST', 'Stock', 'ACHATS')
        ref = cls._generer_reference('SS')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte(compte_charge), 'debit': montant, 'libelle': libelle},
            {'compte': cls._get_compte(compte_stock), 'credit': montant, 'libelle': libelle},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_inventaire(cls, ecart, libelle, compte_stock='31', compte_charge='658',
                                   compte_produit='758', user=None):
        """Correction d'inventaire
           Si ecart positif (surplus): Debit Stock / Credit Produit
           Si ecart negatif (moins-value): Debit Charge / Credit Stock
        """
        journal = cls._get_or_create_journal('ST', 'Stock', 'ACHATS')
        ref = cls._generer_reference('INV')

        if ecart >= 0:
            lignes = [
                {'compte': cls._get_compte(compte_stock), 'debit': ecart, 'libelle': libelle},
                {'compte': cls._get_compte(compte_produit), 'credit': ecart, 'libelle': libelle},
            ]
        else:
            lignes = [
                {'compte': cls._get_compte(compte_charge), 'debit': -ecart, 'libelle': libelle},
                {'compte': cls._get_compte(compte_stock), 'credit': -ecart, 'libelle': libelle},
            ]

        return cls._creer_ecriture(ref, date.today(), libelle, journal, lignes, user=user)

    # ─── Operations d'investissement / immobilisations ─────────

    @classmethod
    @transaction.atomic
    def creer_ecriture_acquisition_immobilisation(cls, montant, libelle, compte_immobilisation,
                                                   compte_tiers=None, caisse=None, user=None):
        """Acquisition: Debit Immobilisation (2x) / Credit Fournisseur (404) ou Caisse"""
        journal = cls._get_or_create_journal('INV', 'Investissements', 'ACHATS')
        ref = cls._generer_reference('ACQ')

        lignes = [
            {'compte': cls._get_compte(compte_immobilisation), 'debit': montant, 'libelle': libelle},
        ]
        if caisse:
            lignes.append({
                'compte': cls._get_compte_caisse(caisse), 'credit': montant, 'libelle': libelle
            })
        elif compte_tiers:
            lignes.append({
                'compte': cls._get_compte(compte_tiers), 'credit': montant, 'libelle': libelle,
                'tiers': compte_tiers if hasattr(compte_tiers, 'compte') else None
            })
        else:
            lignes.append({'compte': cls._get_compte('404'), 'credit': montant, 'libelle': libelle})

        return cls._creer_ecriture(ref, date.today(), libelle, journal, lignes, user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_cession_immobilisation(cls, montant_cession, montant_vnc, libelle,
                                               compte_immobilisation, compte_amortissement,
                                               compte_charge_cession, compte_produit_cession, user=None):
        """Cession: sortie de l'actif, des amortissements, constatation du resultat"""
        journal = cls._get_or_create_journal('INV', 'Investissements', 'ACHATS')
        ref = cls._generer_reference('CESS')
        valeur_originale = montant_vnc + montant_amort_cumule if 'montant_amort_cumule' in dir() else 0

        lignes = [
            {'compte': cls._get_compte(compte_amortissement), 'debit': valeur_originale - montant_vnc,
             'libelle': f"Sortie amortissement {libelle}"},
            {'compte': cls._get_compte(compte_immobilisation), 'credit': valeur_originale,
             'libelle': f"Sortie immobilisation {libelle}"},
        ]

        if montant_cession > montant_vnc:
            plus_value = montant_cession - montant_vnc
            lignes.append({'compte': cls._get_compte('521'), 'debit': montant_cession, 'libelle': 'Prix cession'})
            lignes.append({'compte': cls._get_compte(compte_produit_cession), 'credit': plus_value, 'libelle': 'Plus-value'})
        elif montant_cession > 0:
            moins_value = montant_vnc - montant_cession
            lignes.append({'compte': cls._get_compte('521'), 'debit': montant_cession, 'libelle': 'Prix cession'})
            lignes.append({'compte': cls._get_compte(compte_charge_cession), 'debit': moins_value, 'libelle': 'Moins-value'})

        return cls._creer_ecriture(ref, date.today(), libelle, journal, lignes, user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_amortissement(cls, plan, user=None):
        """Debit: Charge amortissement (68x) / Credit: Amortissement cumule (28x)"""
        immobilisation = plan.immobilisation
        journal = cls._get_or_create_journal('OD', 'Operations Diverses', 'OD')
        ref = f"AMORT-{immobilisation.code}-{plan.periode.strftime('%Y%m')}"
        libelle = f"Amortissement {immobilisation.libelle} - {plan.periode.strftime('%m/%Y')}"

        ecriture = cls._creer_ecriture(ref, plan.periode, libelle, journal, [
            {'compte': immobilisation.compte_charge, 'debit': plan.montant,
             'libelle': f"Amortissement {immobilisation.libelle}"},
            {'compte': immobilisation.compte_amortissement, 'credit': plan.montant,
             'libelle': f"Amortissement {immobilisation.libelle}"},
        ], exercice=cls._get_exercice(plan.periode), user=user)

        plan.ecriture_generee = True
        plan.ecriture_reference = ref
        plan.save()
        return ecriture

    # ─── Operations diverses ───────────────────────────────────

    @classmethod
    @transaction.atomic
    def creer_ecriture_regularisation(cls, montant, libelle, compte_debit, compte_credit, user=None):
        """Ecriture de regularisation manuelle: Debit X / Credit Y"""
        journal = cls._get_or_create_journal('OD', 'Operations Diverses', 'OD')
        ref = cls._generer_reference('RG')

        return cls._creer_ecriture(ref, date.today(), libelle, journal, [
            {'compte': cls._get_compte(compte_debit), 'debit': montant, 'libelle': libelle},
            {'compte': cls._get_compte(compte_credit), 'credit': montant, 'libelle': libelle},
        ], user=user)

    @classmethod
    @transaction.atomic
    def creer_ecriture_cloture_exercice(cls, exercice, resultat, user=None):
        """Affectation du resultat: Debit 12x / Credit 101 ou l'inverse"""
        journal = cls._get_or_create_journal('CL', 'Cloture', 'OD')
        ref = f"RES-{exercice.code}"
        libelle = f"Affectation resultat exercice {exercice.code}"

        if resultat >= 0:
            lignes = [
                {'compte': cls._get_compte('129'), 'debit': resultat,
                 'libelle': f"Benefice {exercice.code}"},
                {'compte': cls._get_compte('101'), 'credit': resultat,
                 'libelle': f"Capital - report benefice {exercice.code}"},
            ]
        else:
            resultat_abs = abs(resultat)
            lignes = [
                {'compte': cls._get_compte('101'), 'debit': resultat_abs,
                 'libelle': f"Imputation perte {exercice.code}"},
                {'compte': cls._get_compte('129'), 'credit': resultat_abs,
                 'libelle': f"Perte {exercice.code}"},
            ]

        return cls._creer_ecriture(ref, exercice.date_fin, libelle, journal, lignes,
                                   exercice=exercice, user=user)


class DepenseEcritureService(EcritureComptableService):
    """Heritage pour retrocompatibilite"""
    pass

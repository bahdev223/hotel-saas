# apps/pos/services/vente_compta_service.py
from decimal import Decimal
from datetime import date
from django.contrib.auth.models import User
from apps.comptabilite.models import EcritureModel, LigneEcritureModel, JournalModel, ExerciceModel, CompteModel


class VenteComptaService:
    """Service pour générer les écritures comptables automatiques des ventes"""
    
    @staticmethod
    def generer_ecriture_vente(vente, user):
        """Génère l'écriture comptable pour une vente POS"""
        
        try:
            # Récupérer l'exercice courant
            exercice = ExerciceModel.objects.filter(
                date_debut__lte=date.today(),
                date_fin__gte=date.today(),
                cloture=False
            ).first()
            
            if not exercice:
                annee = date.today().year
                # 🔥 CORRECTION: Pas de champ 'libelle' dans ExerciceModel
                exercice = ExerciceModel.objects.create(
                    code=str(annee),
                    date_debut=date(annee, 1, 1),
                    date_fin=date(annee, 12, 31),
                    cloture=False
                )
            
            # Récupérer le journal des ventes
            journal, _ = JournalModel.objects.get_or_create(
                code='VT',
                defaults={'libelle': 'Ventes', 'type_journal': 'VENTES', 'actif': True}
            )
            
            # Comptes selon le mode de paiement
            compte_tresorerie = VenteComptaService._get_compte_tresorerie(vente.mode_paiement)
            compte_vente = CompteModel.objects.filter(code='701').first()
            
            if not compte_tresorerie or not compte_vente:
                print(f"⚠️ Comptes non trouvés pour la vente {vente.numero}")
                return None
            
            # Créer l'écriture
            reference = f"V{vente.numero}"
            ecriture = EcritureModel.objects.create(
                reference=reference,
                date_ecriture=date.today(),
                libelle=f"Vente POS - {vente.point_vente.nom} - Ticket {vente.numero}",
                journal=journal,
                piece=vente.numero,
                exercice=exercice,
                validee=True,
                date_validation=date.today(),
                created_by=user.username if hasattr(user, 'username') else str(user)
            )
            
            # Ligne débit (Trésorerie)
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_tresorerie,
                debit=vente.montant_total,
                credit=0,
                libelle=f"Encaissement vente {vente.numero}"
            )
            
            # Ligne crédit (Vente)
            LigneEcritureModel.objects.create(
                ecriture=ecriture,
                compte=compte_vente,
                debit=0,
                credit=vente.montant_total,
                libelle=f"Vente produits - {vente.numero}"
            )
            
            print(f"✅ Écriture comptable générée: {reference}")
            return ecriture
            
        except Exception as e:
            print(f"❌ Erreur génération écriture: {e}")
            return None
    
    @staticmethod
    def _get_compte_tresorerie(mode_paiement):
        """Retourne le compte de trésorerie selon le mode de paiement"""
        comptes = {
            'ESPECES': CompteModel.objects.filter(code='571').first(),
            'CARTE': CompteModel.objects.filter(code='521').first(),
            'MOBILE_MONEY': CompteModel.objects.filter(code='5211').first(),
            'COMPTE_CLIENT': CompteModel.objects.filter(code='411').first(),
            'FACTURE': CompteModel.objects.filter(code='411').first(),
        }
        return comptes.get(mode_paiement, comptes['ESPECES'])
    
    @staticmethod
    def annuler_ecriture_vente(vente, user):
        """Annuler l'écriture comptable d'une vente"""
        try:
            ecriture_originale = EcritureModel.objects.filter(
                piece=vente.numero,
                libelle__icontains="Vente POS"
            ).first()
            
            if not ecriture_originale:
                print(f"⚠️ Aucune écriture trouvée pour la vente {vente.numero}")
                return None
            
            ecriture_originale.validee = False
            ecriture_originale.save()
            
            exercice = ExerciceModel.objects.filter(
                date_debut__lte=date.today(),
                date_fin__gte=date.today(),
                cloture=False
            ).first()
            
            journal, _ = JournalModel.objects.get_or_create(
                code='OD',
                defaults={'libelle': 'Opérations Diverses', 'type_journal': 'OD', 'actif': True}
            )
            
            reference = f"A{vente.numero}"
            ecriture_annul = EcritureModel.objects.create(
                reference=reference,
                date_ecriture=date.today(),
                libelle=f"ANNULATION - Vente {vente.numero}",
                journal=journal,
                piece=vente.numero,
                exercice=exercice,
                validee=True,
                date_validation=date.today(),
                created_by=user.username if hasattr(user, 'username') else str(user)
            )
            
            for ligne in ecriture_originale.lignes.all():
                LigneEcritureModel.objects.create(
                    ecriture=ecriture_annul,
                    compte=ligne.compte,
                    debit=ligne.credit,
                    credit=ligne.debit,
                    libelle=f"Contre-passation: {ligne.libelle}"
                )
            
            print(f"✅ Écriture d'annulation générée: {reference}")
            return ecriture_annul
            
        except Exception as e:
            print(f"❌ Erreur annulation écriture: {e}")
            return None
        
            
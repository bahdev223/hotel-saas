# apps/comptabilite/services/initialisation.py
import json
from decimal import Decimal
from pathlib import Path
import importlib.resources
from django.core.exceptions import ValidationError
from ..models import CompteModel


class InitialisationComptable:
    """Service d'initialisation du plan comptable SYSCOHADA"""
    
    def __init__(self):
        # 🔥 Charger depuis le package installé comptabilite_sahel
        try:
            # Essayer de charger via importlib.resources
            self.json_content = importlib.resources.files('comptabilite_sahel.syscohada').joinpath('plan_comptable.json').read_text(encoding='utf-8')
            self.json_path = None
            print("✅ Plan comptable chargé depuis le package comptabilite_sahel")
        except (ImportError, FileNotFoundError):
            # Fallback: chercher dans le système de fichiers
            possible_paths = [
                Path('C:/Users/bah.dev/Desktop/hotel/comptabilite_sahel/comptabilite_sahel/syscohada/plan_comptable.json'),
                Path(__file__).parent.parent.parent.parent / 'comptabilite_sahel' / 'comptabilite_sahel' / 'syscohada' / 'plan_comptable.json',
            ]
            
            self.json_path = None
            for path in possible_paths:
                if path.exists():
                    self.json_path = path
                    break
            
            if not self.json_path:
                raise FileNotFoundError("Impossible de trouver le fichier plan_comptable.json")
            
            with open(self.json_path, 'r', encoding='utf-8') as f:
                self.json_content = f.read()
            
            print(f"✅ Plan comptable chargé depuis: {self.json_path}")
    
    def charger_plan_comptable(self):
        """
        Charger le plan comptable depuis le JSON
        """
        return json.loads(self.json_content)
    
    def importer_comptes(self, force=False):
        """
        Importer tous les comptes dans la base de données
        """
        if force:
            # Supprimer les comptes existants
            CompteModel.objects.all().delete()
            print("🗑️ Anciens comptes supprimés")
        
        data = self.charger_plan_comptable()
        comptes_data = data.get('comptes', [])
        
        if not comptes_data:
            print("⚠️ Aucun compte à importer")
            return {}
        
        # Dictionnaire pour stocker les objets créés
        comptes_crees = {}
        
        total = len(comptes_data)
        print(f"📊 Début de l'importation de {total} comptes...")
        
        for i, compte_data in enumerate(comptes_data, 1):
            code = compte_data['code']
            libelle = compte_data['libelle']
            parent_code = compte_data.get('parent')
            
            # Récupérer le parent si spécifié
            parent = None
            if parent_code and parent_code in comptes_crees:
                parent = comptes_crees[parent_code]
            
            # Déterminer le niveau
            niveau = compte_data.get('niveau', len(code))
            
            # Déterminer le type de compte
            type_compte = compte_data.get('type', 'compte')
            
            # Créer ou mettre à jour le compte
            compte, created = CompteModel.objects.update_or_create(
                code=code,
                defaults={
                    'libelle': libelle,
                    'parent': parent,
                    'niveau': niveau,
                    'nature': compte_data.get('nature', 'MIXTE'),
                    'sens': compte_data.get('sens', 'MIXTE'),
                    'type_compte': type_compte,
                    'est_mouvement': compte_data.get('est_mouvement', True),
                    'categorie': compte_data.get('categorie', 'bilan'),
                    'actif': True
                }
            )
            
            comptes_crees[code] = compte
            
            if created:
                print(f"✅ {code} - {libelle}")
        
        print(f"\n🎉 Importation terminée: {len(comptes_crees)} comptes")
        return comptes_crees
    
    def verifier_plan_comptable(self):
        """
        Vérifier l'intégrité du plan comptable chargé
        """
        data = self.charger_plan_comptable()
        comptes = data.get('comptes', [])
        
        erreurs = []
        codes_connus = set()
        
        for compte in comptes:
            code = compte.get('code')
            libelle = compte.get('libelle')
            parent = compte.get('parent')
            
            if not code:
                erreurs.append(f"Compte sans code: {compte}")
                continue
            
            if not libelle:
                erreurs.append(f"Compte {code} sans libellé")
            
            if code in codes_connus:
                erreurs.append(f"Code dupliqué: {code}")
            codes_connus.add(code)
            
            if parent and parent not in codes_connus and parent != 'null':
                pass
        
        if erreurs:
            print(f"⚠️ {len(erreurs)} erreurs trouvées:")
            for err in erreurs[:10]:
                print(f"   - {err}")
        else:
            print("✅ Plan comptable valide")
        
        return erreurs
    
    def get_stats(self):
        """
        Statistiques du plan comptable en base
        """
        stats = {
            'total': CompteModel.objects.count(),
            'classes': CompteModel.objects.filter(type_compte='classe').count(),
            'groupes': CompteModel.objects.filter(type_compte='groupe').count(),
            'comptes': CompteModel.objects.filter(type_compte='compte').count(),
            'sous_comptes': CompteModel.objects.filter(type_compte='sous_compte').count(),
            'actif': CompteModel.objects.filter(actif=True).count(),
            'inactif': CompteModel.objects.filter(actif=False).count(),
        }
        
        # Par classe
        for i in range(1, 10):
            stats[f'classe_{i}'] = CompteModel.objects.filter(code__startswith=str(i)).count()
        
        return stats
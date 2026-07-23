# apps/comptabilite/management/commands/charger_plan_comptable.py
"""
Commande Django pour charger le plan comptable SYSCOHADA
Version corrigée pour utiliser les objets Compte de comptabilite_sahel
"""

from django.core.management.base import BaseCommand
from django.apps import apps
from django.db import transaction


class Command(BaseCommand):
    help = 'Charge le plan comptable SYSCOHADA dans la base Django'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force le rechargement même si des comptes existent',
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('📋 CHARGEMENT DU PLAN COMPTABLE SYSCOHADA'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        force = options['force']
        
        try:
            # 1. Importer le chargeur
            from comptabilite_sahel.syscohada.chargeur import ChargeurPlanComptable
            self.stdout.write('✅ comptabilite_sahel trouvé')
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'❌ Erreur: {e}'))
            return
        
        # 2. Récupérer le modèle Django
        CompteModel = apps.get_model('comptabilite', 'CompteModel')
        
        # 3. Vérifier si des comptes existent déjà
        comptes_existants = CompteModel.objects.count()
        
        if comptes_existants > 0 and not force:
            self.stdout.write(self.style.WARNING(f'⚠️ {comptes_existants} comptes existent déjà.'))
            self.stdout.write('   Utilisez --force pour recharger.')
            return
        
        # 4. Supprimer les comptes si force
        if force and comptes_existants > 0:
            self.stdout.write(f'🗑️ Suppression des {comptes_existants} comptes existants...')
            CompteModel.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('   ✅ Suppression terminée'))
        
        # 5. Charger le plan comptable
        self.stdout.write('📖 Chargement du fichier plan_comptable.json...')
        chargeur = ChargeurPlanComptable()
        comptes_objets = chargeur.charger()  # Retourne une liste d'objets Compte
        
        self.stdout.write(self.style.SUCCESS(f'   ✅ {len(comptes_objets)} comptes chargés depuis le JSON'))
        
        # 6. Insérer les comptes dans Django
        self.stdout.write('💾 Insertion dans la base Django...')
        
        comptes_crees = 0
        parents_cache = {}  # code -> objet Django
        
        with transaction.atomic():
            for compte_obj in comptes_objets:
                try:
                    # Les attributs de l'objet Compte de comptabilite_sahel
                    code = compte_obj.code
                    libelle = compte_obj.libelle
                    parent_code = compte_obj.parent if hasattr(compte_obj, 'parent') else None
                    niveau = compte_obj.niveau if hasattr(compte_obj, 'niveau') else len(code)
                    type_compte = compte_obj.type if hasattr(compte_obj, 'type') else 'compte'
                    nature = compte_obj.nature if hasattr(compte_obj, 'nature') else 'MIXTE'
                    est_mouvement = compte_obj.est_mouvement if hasattr(compte_obj, 'est_mouvement') else True
                    categorie = compte_obj.categorie if hasattr(compte_obj, 'categorie') else 'bilan'
                    
                    if not code or not libelle:
                        continue
                    
                    # Déterminer le sens (DEBIT/CREDIT)
                    if nature in ['ACTIF', 'CHARGE']:
                        sens = 'DEBIT'
                    elif nature in ['PASSIF', 'PRODUIT']:
                        sens = 'CREDIT'
                    else:
                        sens = 'MIXTE'
                    
                    # Récupérer le parent depuis le cache
                    parent = None
                    if parent_code and parent_code in parents_cache:
                        parent = parents_cache[parent_code]
                    
                    # Créer le compte dans Django
                    compte, created = CompteModel.objects.get_or_create(
                        code=code,
                        defaults={
                            'libelle': libelle[:200],
                            'nature': nature,
                            'sens': sens,
                            'parent': parent,
                            'niveau': niveau,
                            'type_compte': type_compte,
                            'est_mouvement': est_mouvement,
                            'categorie': categorie if categorie else ('bilan' if code and code[0] in ['1', '2', '3', '4', '5'] else 'resultat'),
                            'actif': True
                        }
                    )
                    
                    if created:
                        comptes_crees += 1
                        parents_cache[code] = compte
                        
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'   ⚠️ Erreur sur compte {getattr(compte_obj, "code", "?")}: {str(e)}'))
        
        # 7. Afficher le résultat
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('📊 RÉSULTAT DU CHARGEMENT'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(f'✅ Comptes créés: {comptes_crees}')
        
        # 8. Afficher la répartition par classe
        self.stdout.write('')
        self.stdout.write('📊 RÉPARTITION PAR CLASSE :')
        
        classes_libelles = {
            '1': 'RESSOURCES DURABLES (Capital)',
            '2': 'ACTIFS IMMOBILISÉS',
            '3': 'STOCKS',
            '4': 'TIERS',
            '5': 'TRÉSORERIE',
            '6': 'CHARGES',
            '7': 'PRODUITS',
            '8': 'RÉSULTATS',
            '9': 'HORS BILAN'
        }
        
        total = CompteModel.objects.count()
        for i in range(1, 10):
            classe = str(i)
            count = CompteModel.objects.filter(code__startswith=classe).count()
            if count > 0:
                pourcentage = (count / total) * 100 if total > 0 else 0
                libelle = classes_libelles.get(classe, f'Classe {classe}')
                self.stdout.write(f'   📁 Classe {classe} - {libelle}')
                self.stdout.write(f'      {count} comptes ({pourcentage:.1f}%)')
        
        # 9. Afficher quelques comptes racines
        self.stdout.write('')
        self.stdout.write('📌 COMPTES RACINES (niveau 1) :')
        comptes_racines = CompteModel.objects.filter(niveau=1, parent__isnull=True)[:10]
        for compte in comptes_racines:
            self.stdout.write(f'   • {compte.code} - {compte.libelle[:50]}')
        
        # 10. Résumé final
        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS('=' * 60))
        self.stdout.write(self.style.SUCCESS('✅ CHARGEMENT TERMINÉ AVEC SUCCÈS'))
        self.stdout.write(self.style.SUCCESS('=' * 60))
        
        
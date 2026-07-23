# apps/rh/management/commands/init_rh_data.py

from django.core.management.base import BaseCommand
from apps.rh.models import Departement, Poste


class Command(BaseCommand):
    help = "Initialise les départements et postes RH par défaut"

    def handle(self, *args, **kwargs):

        departements = [
            ("DIR", "Direction"),
            ("REC", "Réception"),
            ("HK", "Housekeeping"),
            ("RES", "Restaurant"),
            ("BAR", "Bar"),
            ("KIT", "Cuisine"),
            ("STO", "Stock & Économat"),
            ("COM", "Comptabilité"),
            ("RH", "Ressources Humaines"),
            ("SEC", "Sécurité"),
            ("TEC", "Maintenance Technique"),
            ("SPA", "Spa & Bien-être"),
            ("EVT", "Événementiel"),
            ("MKT", "Commercial & Marketing"),
            ("IT", "Informatique"),
        ]

        postes = [
            ("DG", "Directeur Général", "Cadre"),
            ("DIRHOT", "Directeur Hôtel", "Cadre"),
            ("ASDIR", "Assistant Direction", "Employe"),

            ("RECEP", "Réceptionniste", "Employe"),
            ("CHREC", "Chef Réception", "AgentMaitrise"),
            ("CAIS", "Caissier", "Employe"),
            ("NIGHT", "Night Auditor", "Technicien"),

            ("FCH", "Femme de chambre", "Ouvrier"),
            ("GOUV", "Gouvernante", "AgentMaitrise"),
            ("CGOUV", "Chef Gouvernante", "Cadre"),
            ("LING", "Lingère", "Employe"),

            ("SERV", "Serveur", "Employe"),
            ("BARM", "Barman", "Employe"),
            ("MHD", "Maître d'hôtel", "AgentMaitrise"),
            ("RRES", "Responsable Restaurant", "Cadre"),

            ("CHEF", "Chef Cuisinier", "Cadre"),
            ("SOUS", "Sous-chef", "AgentMaitrise"),
            ("COMMIS", "Commis Cuisine", "Ouvrier"),
            ("PAT", "Pâtissier", "Technicien"),

            ("COMPT", "Comptable", "Cadre"),
            ("CGEN", "Caissier Général", "AgentMaitrise"),
            ("CFIN", "Contrôleur Financier", "Cadre"),

            ("RRH", "Responsable RH", "Cadre"),
            ("ARH", "Assistant RH", "Employe"),

            ("TECH", "Technicien Maintenance", "Technicien"),
            ("ELEC", "Électricien", "Technicien"),
            ("PLOM", "Plombier", "Technicien"),

            ("SECU", "Agent Sécurité", "Employe"),
            ("SUPSEC", "Superviseur Sécurité", "AgentMaitrise"),
        ]

        # Création départements
        for code, libelle in departements:
            obj, created = Departement.objects.get_or_create(
                code=code,
                defaults={
                    "libelle": libelle,
                    "actif": True
                }
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Département créé : {libelle}")
                )

        # Création postes
        for code, intitule, classification in postes:
            obj, created = Poste.objects.get_or_create(
                code=code,
                defaults={
                    "intitule": intitule,
                    "classification": classification
                }
            )

            if created:
                self.stdout.write(
                    self.style.SUCCESS(f"✅ Poste créé : {intitule}")
                )

        self.stdout.write(
            self.style.SUCCESS("🎉 Initialisation RH terminée avec succès.")
        )
        
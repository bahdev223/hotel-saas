from django.core.management.base import BaseCommand
from django.contrib.auth.models import User, Group, Permission
from django.db import transaction
from decimal import Decimal


class Command(BaseCommand):
    help = "Seed les donnees de base : admin, entreprise, employes"

    def handle(self, *args, **kwargs):
        self._create_groups()
        self._create_rh_data()
        entreprise = self._create_enterprise()
        admin = self._create_admin()
        self._create_employees(entreprise)
        self.stdout.write(self.style.SUCCESS("\nSeed terminee avec succes !"))
        self.stdout.write("Connecte-toi avec admin / admin123")

    def _create_groups(self):
        from apps.setup_roles import POSTE_GROUP_MAPPING, GROUP_PERMISSIONS

        groupes = set(POSTE_GROUP_MAPPING.values())
        for nom in groupes:
            group, created = Group.objects.get_or_create(name=nom)
            if created:
                self.stdout.write(f"  [+] Groupe cree : {nom}")

        patron = Group.objects.get(name="PATRON")
        patron.permissions.set(Permission.objects.all())
        self.stdout.write(f"  [*] PATRON : {patron.permissions.count()} permissions")

        for group_name, actions in GROUP_PERMISSIONS.items():
            if group_name == "PATRON":
                continue
            group = Group.objects.get(name=group_name)
            from django.db.models import Q
            q = Q()
            for action in actions:
                q |= Q(codename__startswith=action)
            perms = Permission.objects.filter(q)
            group.permissions.set(perms)
            self.stdout.write(f"  [+] {group_name} : {perms.count()} permissions")

    def _create_rh_data(self):
        from apps.rh.models import Departement, Poste

        deps = [
            ("DIR", "Direction"), ("COM", "Comptabilite"), ("RES", "Restaurant"),
            ("KIT", "Cuisine"), ("CAI", "Caisse"),
        ]
        for code, lib in deps:
            Departement.objects.get_or_create(code=code, defaults={"libelle": lib, "actif": True})

        postes = [
            ("COMPT", "Comptable", "Cadre"),
            ("COMMIS", "Commis Cuisine", "Ouvrier"),
            ("SERV", "Serveur", "Employe"),
            ("CAIS", "Caissier", "Employe"),
            ("RRES", "Responsable Restaurant", "Cadre"),
        ]
        for code, titre, cla in postes:
            Poste.objects.get_or_create(code=code, defaults={"intitule": titre, "classification": cla})

        self.stdout.write("  [+] Donnees RH initialisees")

    def _create_enterprise(self):
        from apps.entreprises.services import creer_installation_complete
        from apps.entreprises.models import Entreprise

        if Entreprise.objects.filter(actif=True).exists():
            ent = Entreprise.objects.filter(actif=True).first()
            self.stdout.write(f"  [/] Entreprise deja existante : {ent.nom}")
            return ent

        entreprise, etablissement = creer_installation_complete(
            nom_entreprise="Hotel Le Royal",
            code_entreprise="ROYAL",
            nom_etablissement="Hotel Le Royal - Centre",
            code_etablissement="ROYAL-C",
            telephone="+223 20 00 00 00",
            email="contact@hotel-royal.ml",
            ville="Bamako",
            pays="Mali",
        )
        self.stdout.write(f"  [+] Entreprise creee : {entreprise.nom}")
        return entreprise

    def _create_admin(self):
        user, created = User.objects.get_or_create(
            username="admin",
            defaults={"email": "admin@hotel-royal.ml", "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password("admin123")
            user.save()
            self.stdout.write("  [+] Superuser admin cree")
        else:
            user.set_password("admin123")
            user.save()
            self.stdout.write("  [/] admin existant, mot de passe reinitialise")

        try:
            patron = Group.objects.get(name="PATRON")
            user.groups.add(patron)
        except Group.DoesNotExist:
            pass

        return user

    def _create_employees(self, entreprise):
        from django.contrib.auth.models import User, Group
        from apps.rh.models import Employe, Poste, Departement

        employees_data = [
            ("Kadiatou", "Diallo", "COMPT", "COM", "comptable", "COMPTABLE"),
            ("Mamadou", "Traore", "COMMIS", "KIT", "cuisinier1", "CUISINE"),
            ("Fatoumata", "Cisse", "COMMIS", "KIT", "cuisinier2", "CUISINE"),
            ("Sekou", "Keita", "COMMIS", "KIT", "cuisinier3", "CUISINE"),
            ("Aminata", "Sow", "SERV", "RES", "serveur1", "RESTAURANT"),
            ("Ousmane", "Diakite", "SERV", "RES", "serveur2", "RESTAURANT"),
            ("Rokia", "Coulibaly", "CAIS", "CAI", "caissiere1", "CAISSIER"),
            ("Mariam", "Kone", "CAIS", "CAI", "caissiere2", "CAISSIER"),
            ("Drissa", "Ballo", "RRES", "RES", "manager", "MANAGER"),
        ]

        for prenom, nom, poste_code, dep_code, username, group_name in employees_data:
            if User.objects.filter(username=username).exists():
                self.stdout.write(f"  [/] {prenom} {nom} deja existant")
                continue

            user = User.objects.create_user(
                username=username,
                password="1234",
                first_name=prenom,
                last_name=nom,
                is_staff=True,
            )
            try:
                group = Group.objects.get(name=group_name)
                user.groups.add(group)
            except Group.DoesNotExist:
                pass

            poste = Poste.objects.filter(code=poste_code).first()
            departement = Departement.objects.filter(code=dep_code).first()

            Employe.objects.create(
                user=user,
                nom=nom,
                prenom=prenom,
                poste=poste,
                departement=departement,
                actif=True,
            )
            self.stdout.write(f"  [+] {prenom} {nom} ({group_name}) cree")

        self.stdout.write(f"  [+] {len(employees_data)} employes crees")

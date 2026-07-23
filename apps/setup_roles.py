# apps/setup_roles.py

import os
import sys
import django

# Config Django
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_project.settings')
django.setup()

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


# 🔥 Mapping Poste → Groupe
POSTE_GROUP_MAPPING = {

    # Direction
    'DG': 'PATRON',
    'DIRHOT': 'MANAGER',
    'ASDIR': 'MANAGER',

    # Réception
    'RECEP': 'RECEPTION',
    'CHREC': 'MANAGER',
    'NIGHT': 'RECEPTION',

    # Caisse
    'CAIS': 'CAISSIER',
    'CGEN': 'CAISSIER',

    # Restaurant / Bar
    'SERV': 'RESTAURANT',
    'BARM': 'BAR',
    'MHD': 'RESTAURANT',
    'RRES': 'MANAGER',

    # Cuisine
    'CHEF': 'CUISINE',
    'SOUS': 'CUISINE',
    'COMMIS': 'CUISINE',
    'PAT': 'CUISINE',

    # Stock
    'STO': 'STOCK',

    # Comptabilité
    'COMPT': 'COMPTABLE',
    'CFIN': 'COMPTABLE',

    # RH
    'RRH': 'RH',
    'ARH': 'RH',

    # Technique
    'TECH': 'TECHNIQUE',
    'ELEC': 'TECHNIQUE',
    'PLOM': 'TECHNIQUE',

    # Sécurité
    'SECU': 'SECURITE',
    'SUPSEC': 'SECURITE',

    # Promoteur / Propriétaire
    'PROM': 'PROMOTEUR',

    # RAF — Responsable Administratif et Financier
    'RAF': 'RAF',
}


# 🔥 Permissions par groupe
GROUP_PERMISSIONS = {

    'PATRON': ['add', 'change', 'delete', 'view'],

    'MANAGER': ['add', 'change', 'view'],

    'RECEPTION': ['view', 'add', 'change'],

    'CAISSIER': ['view', 'add'],

    'CUISINE': ['view'],

    'STOCK': ['view', 'add', 'change'],

    'COMPTABLE': ['view', 'add', 'change'],

    'RH': ['view', 'add', 'change'],

    'TECHNIQUE': ['view'],

    'SECURITE': ['view'],
    'PROMOTEUR': ['view'],
    'RAF': ['view', 'add', 'change', 'delete'],
}


def create_default_groups():
    """Créer groupes et permissions"""

    groupes_uniques = set(POSTE_GROUP_MAPPING.values())

    print("\n📁 Création des groupes...")

    for nom in groupes_uniques:

        group, created = Group.objects.get_or_create(name=nom)

        if created:
            print(f"✅ Groupe créé : {nom}")
        else:
            print(f"⏭️ Groupe existe déjà : {nom}")

    # 🔥 PATRON = toutes permissions
    patron = Group.objects.get(name='PATRON')
    toutes_permissions = Permission.objects.all()
    patron.permissions.set(toutes_permissions)

    print(f"\n👑 PATRON reçoit {toutes_permissions.count()} permissions")

    # 🔥 Config permissions autres groupes
    for group_name, actions in GROUP_PERMISSIONS.items():

        if group_name == 'PATRON':
            continue

        group = Group.objects.get(name=group_name)

        permissions = Permission.objects.filter(
            codename__startswith=tuple(actions)
        )

        group.permissions.set(permissions)

        print(
            f"🔐 {group_name} → {permissions.count()} permissions"
        )

    print("\n🎉 Configuration des rôles terminée.")


def add_user_to_group(username, group_name='PATRON'):
    """Ajouter utilisateur à groupe"""

    from django.contrib.auth.models import User

    try:
        user = User.objects.get(username=username)

        group = Group.objects.get(name=group_name)

        user.groups.add(group)

        user.save()

        print(f"✅ {username} ajouté à {group_name}")

        return True

    except User.DoesNotExist:
        print(f"❌ Utilisateur {username} non trouvé")

    except Group.DoesNotExist:
        print(f"❌ Groupe {group_name} non trouvé")

    return False


if __name__ == "__main__":

    create_default_groups()

    # Exemple
    # add_user_to_group('admin', 'PATRON')
    
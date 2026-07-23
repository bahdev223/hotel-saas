from django.db import migrations
from datetime import date


def setup_raf_employe(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Employe = apps.get_model('rh', 'Employe')

    try:
        user = User.objects.get(username='raf')
    except User.DoesNotExist:
        return

    # Vérifier si l'employé existe déjà
    if Employe.objects.filter(user=user).exists():
        return

    # Générer le prochain matricule
    annee = date.today().year
    prefix = f"RD-{annee}-"
    dernier = Employe.objects.filter(matricule__startswith=prefix).order_by('matricule').last()
    if dernier and dernier.matricule:
        try:
            num = int(dernier.matricule.rsplit('-', 1)[-1]) + 1
        except (ValueError, IndexError):
            num = 1
    else:
        num = 1
    matricule = f"{prefix}{num:04d}"

    Employe.objects.create(
        user=user,
        matricule=matricule,
        nom='RAF',
        prenom='Agent',
        email=user.email or 'raf@hotel.local',
        telephone='0000000000',
        actif=True,
        # Pas de point_vente — le RAF n'en a pas de fixe
        point_vente=None,
    )


def reverse_raf_employe(apps, schema_editor):
    User = apps.get_model('auth', 'User')
    Employe = apps.get_model('rh', 'Employe')
    try:
        user = User.objects.get(username='raf')
        Employe.objects.filter(user=user).delete()
    except User.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0014_setup_raf_guichet'),
        ('rh', '0004_alter_employe_matricule'),
    ]

    operations = [
        migrations.RunPython(setup_raf_employe, reverse_raf_employe),
    ]

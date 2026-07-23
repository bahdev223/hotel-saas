from django.db import migrations


def setup_raf_guichet(apps, schema_editor):
    CompteModel = apps.get_model('comptabilite', 'CompteModel')
    Caisse = apps.get_model('tresorerie', 'Caisse')
    PointVente = apps.get_model('pos', 'PointVente')
    PointVenteEntrepot = apps.get_model('pos', 'PointVenteEntrepot')
    Entrepot = apps.get_model('stock', 'Entrepot')
    Group = apps.get_model('auth', 'Group')
    Permission = apps.get_model('auth', 'Permission')
    ContentType = apps.get_model('contenttypes', 'ContentType')

    # 1. Compte comptable 571001 (sous-compte de 571 CAISSE SIEGE SOCIAL)
    parent_571 = CompteModel.objects.filter(code='571').first()
    if not parent_571:
        # Les données comptables n'ont pas encore été chargées (loaddata)
        return

    compte_571001, _ = CompteModel.objects.get_or_create(
        code='571001',
        defaults={
            'libelle': 'CAISSE CENTRALE RAF',
            'nature': 'ACTIF',
            'sens': 'DEBIT',
            'parent': parent_571,
            'niveau': 3,
            'type_compte': 'compte',
            'est_mouvement': True,
            'categorie': 'bilan',
            'actif': True,
        }
    )

    # 2. Caisse RAF-001
    caisse_raf, _ = Caisse.objects.get_or_create(
        code='RAF-001',
        defaults={
            'nom': 'Caisse Centrale RAF',
                'type_financier': 'ESPECES',
                'role': 'CENTRALE',
            'solde': 0,
            'actif': True,
            'compte_comptable': compte_571001,
        }
    )

    # 3. PointVente RAF
    point_vente, _ = PointVente.objects.get_or_create(
        code='RAF',
        defaults={
            'nom': 'Guichet RAF',
            'emplacement': 'GUICHET',
            'actif': True,
            'caisse': caisse_raf,
            'entrepot': None,
        }
    )

    # 4. Lier aux entrepôts Brasserie et Restaurant
    for type_ep in ['BRASSERIE', 'RESTAURANT']:
        entrepot = Entrepot.objects.filter(type_entrepot=type_ep, actif=True).first()
        if entrepot:
            PointVenteEntrepot.objects.get_or_create(
                point_vente=point_vente, entrepot=entrepot
            )

    # 5. Groupe RAF
    Group.objects.get_or_create(name='RAF')

    # 6. Permissions minimales
    raf_group = Group.objects.get(name='RAF')
    pos_ct = ContentType.objects.get_for_model(PointVente)
    for codename in ['view_pointvente', 'change_pointvente']:
        try:
            perm = Permission.objects.get(codename=codename, content_type=pos_ct)
            raf_group.permissions.add(perm)
        except Permission.DoesNotExist:
            pass


def reverse_raf_guichet(apps, schema_editor):
    PointVenteEntrepot = apps.get_model('pos', 'PointVenteEntrepot')
    PointVente = apps.get_model('pos', 'PointVente')
    Caisse = apps.get_model('tresorerie', 'Caisse')
    CompteModel = apps.get_model('comptabilite', 'CompteModel')

    PointVenteEntrepot.objects.filter(point_vente__code='RAF').delete()
    PointVente.objects.filter(code='RAF').delete()
    Caisse.objects.filter(code='RAF-001').delete()
    CompteModel.objects.filter(code='571001').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('pos', '0013_alter_pointvente_emplacement_pointventeentrepot'),
        ('tresorerie', '0003_caisse_caisse_centrale_alter_caisse_type'),
        ('stock', '0014_seed_brasserie_entrepot_initial'),
        ('comptabilite', '0006_alter_comptefournisseur_fournisseur'),
    ]

    operations = [
        migrations.RunPython(setup_raf_guichet, reverse_raf_guichet),
    ]

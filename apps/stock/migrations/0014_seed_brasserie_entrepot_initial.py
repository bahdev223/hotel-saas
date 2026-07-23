from django.db import migrations


def crear_entrepot_brasserie(apps, schema_editor):
    Entrepot = apps.get_model('stock', 'Entrepot')
    if not Entrepot.objects.filter(type_entrepot='BRASSERIE').exists():
        Entrepot.objects.create(
            code='BRS-001',
            nom='Brasserie',
            type_entrepot='BRASSERIE',
            actif=True,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('stock', '0013_add_brasserie_entrepot_type'),
    ]

    operations = [
        migrations.RunPython(crear_entrepot_brasserie, migrations.RunPython.noop),
    ]

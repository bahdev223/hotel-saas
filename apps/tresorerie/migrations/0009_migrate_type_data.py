from django.db import migrations

def migrate_type_data(apps, schema_editor):
    Caisse = apps.get_model('tresorerie', 'Caisse')
    for c in Caisse.objects.all():
        # Ancien type → nouveau type_financier + role
        old = c.type if hasattr(c, 'type') else ''
        if old in ('CENTRALE', 'POINT_VENTE'):
            c.type_financier = 'ESPECES'
            c.role = old
        elif old == 'BANQUE':
            c.type_financier = 'BANQUE'
            c.role = None
        else:
            c.type_financier = 'ESPECES'
            c.role = None
        c.save()


class Migration(migrations.Migration):
    dependencies = [
        ('tresorerie', '0008_alter_caisse_options_remove_caisse_type_caisse_role_and_more'),
    ]
    operations = [
        migrations.RunPython(migrate_type_data),
    ]

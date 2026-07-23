from django.db import migrations

def convert_banque_to_centrale(apps, schema_editor):
    Caisse = apps.get_model('tresorerie', 'Caisse')
    qs = Caisse.objects.filter(type='BANQUE')
    count = qs.count()
    qs.update(type='CENTRALE', actif=False)
    if count:
        print(f"\n   ✅ {count} caisse(s) BANQUE convertie(s) en CENTRALE (désactivée)")


class Migration(migrations.Migration):
    dependencies = [
        ('tresorerie', '0006_alter_caisse_type'),
    ]
    operations = [
        migrations.RunPython(convert_banque_to_centrale),
    ]

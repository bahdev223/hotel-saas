from django.db import migrations, models


def remplir_telephones_vides(apps, schema_editor):
    Client = apps.get_model('clients', 'Client')
    Client.objects.filter(telephone__isnull=True).update(telephone='0000000000')
    Client.objects.filter(telephone='').update(telephone='0000000000')


class Migration(migrations.Migration):

    dependencies = [
        ('clients', '0002_client_delete_clientmodel_and_more'),
    ]

    operations = [
        migrations.RunPython(remplir_telephones_vides, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='client',
            name='telephone',
            field=models.CharField(max_length=20),
        ),
    ]

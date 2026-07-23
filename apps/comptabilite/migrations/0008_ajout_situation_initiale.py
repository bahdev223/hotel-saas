# Generated manually — Assistant de mise en service

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('comptabilite', '0007_parametreentreprise_compte_contrepartie_stock'),
    ]

    operations = [
        migrations.AddField(
            model_name='configurationentreprise',
            name='situation_initiale_validee',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='configurationentreprise',
            name='date_validation_situation',
            field=models.DateTimeField(null=True, blank=True),
        ),
        migrations.AddField(
            model_name='configurationentreprise',
            name='contrepartie_situation',
            field=models.CharField(default='101', max_length=20),
        ),
        migrations.AddField(
            model_name='configurationentreprise',
            name='mode_demarrage',
            field=models.BooleanField(default=True),
        ),
    ]

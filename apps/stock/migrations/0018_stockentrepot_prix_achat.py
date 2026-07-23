from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('stock', '0017_seed_domaines'),
    ]

    operations = [
        migrations.AddField(
            model_name='stockentrepot',
            name='prix_achat',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=15, verbose_name="Prix d'achat unitaire"),
        ),
    ]

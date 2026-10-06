from django.db import migrations, models
from django.db.models import F, Q


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0008_backfill_pos_role_permissions"),
    ]

    operations = [
        migrations.AddConstraint(
            model_name="horaireaffectation",
            constraint=models.CheckConstraint(
                condition=~Q(heure_debut=F("heure_fin")),
                name="horaire_pos_debut_fin_differents",
            ),
        ),
    ]

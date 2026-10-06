from django.db import migrations, models


def backfill_restaurant_permissions(apps, schema_editor):
    Affectation = apps.get_model("pos", "AffectationPointVente")

    Affectation.objects.filter(role="SERVEUR").update(
        peut_gerer_salle=True,
        peut_servir_commande=True,
    )
    Affectation.objects.filter(role="PREPARATEUR").update(
        peut_gerer_cuisine=True,
    )
    Affectation.objects.filter(role__in=["RESPONSABLE", "SUPERVISEUR"]).update(
        peut_gerer_salle=True,
        peut_gerer_cuisine=True,
        peut_servir_commande=True,
    )


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0010_session_caisse_v2"),
    ]

    operations = [
        migrations.AddField(
            model_name="affectationpointvente",
            name="peut_gerer_salle",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="affectationpointvente",
            name="peut_gerer_cuisine",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="affectationpointvente",
            name="peut_servir_commande",
            field=models.BooleanField(default=False),
        ),
        migrations.RunPython(
            backfill_restaurant_permissions,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

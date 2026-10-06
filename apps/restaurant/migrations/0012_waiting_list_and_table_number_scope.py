from django.db import migrations, models
import django.db.models.deletion


def backfill_waiting_list_point(apps, schema_editor):
    FileAttente = apps.get_model("restaurant", "FileAttenteModel")
    PointVente = apps.get_model("pos", "PointVente")

    restaurants = list(
        PointVente.objects.filter(type="RESTAURATION", actif=True).order_by("id")
    )
    if len(restaurants) == 1:
        FileAttente.objects.filter(point_vente__isnull=True).update(
            point_vente=restaurants[0]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("restaurant", "0011_salles_tables_operational"),
        ("pos", "0011_restaurant_operational_permissions"),
    ]

    operations = [
        migrations.AddField(
            model_name="fileattentemodel",
            name="point_vente",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="file_attente_restaurant",
                to="pos.pointvente",
            ),
        ),
        migrations.AlterField(
            model_name="tablemodel",
            name="numero",
            field=models.CharField(max_length=10),
        ),
        migrations.AddConstraint(
            model_name="tablemodel",
            constraint=models.UniqueConstraint(
                fields=("salle", "numero"),
                name="unique_table_numero_par_salle",
            ),
        ),
        migrations.RunPython(
            backfill_waiting_list_point,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

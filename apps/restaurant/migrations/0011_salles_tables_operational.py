from django.db import migrations, models
import django.db.models.deletion


def backfill_single_restaurant_room(apps, schema_editor):
    PointVente = apps.get_model("pos", "PointVente")
    Salle = apps.get_model("restaurant", "SalleModel")
    Table = apps.get_model("restaurant", "TableModel")

    restaurants = list(
        PointVente.objects.filter(type="RESTAURATION", actif=True).order_by("id")
    )
    if len(restaurants) != 1:
        return

    point = restaurants[0]
    salles_by_name = {}
    for table in Table.objects.filter(salle__isnull=True).order_by("id"):
        name = (table.zone or "Salle principale").strip() or "Salle principale"
        key = name.lower()
        salle = salles_by_name.get(key)
        if salle is None:
            code_base = "".join(ch for ch in name.upper() if ch.isalnum())[:20] or "SALLE"
            code = code_base
            suffix = 1
            while Salle.objects.filter(point_vente=point, code=code).exists():
                suffix += 1
                code = f"{code_base[:16]}-{suffix}"
            salle = Salle.objects.create(
                point_vente=point,
                code=code,
                nom=name,
                ordre=len(salles_by_name),
                actif=True,
            )
            salles_by_name[key] = salle
        table.salle = salle
        table.save(update_fields=["salle"])


class Migration(migrations.Migration):
    dependencies = [
        ("restaurant", "0010_productioningredient_cout_unitaire_and_more"),
        ("pos", "0011_restaurant_operational_permissions"),
        ("rh", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="SalleModel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("code", models.CharField(max_length=30)),
                ("nom", models.CharField(max_length=100)),
                ("ordre", models.PositiveSmallIntegerField(default=0)),
                ("actif", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("point_vente", models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name="salles_restaurant",
                    to="pos.pointvente",
                )),
            ],
            options={
                "verbose_name": "Salle",
                "verbose_name_plural": "Salles",
                "db_table": "restaurant_salles",
                "ordering": ["ordre", "nom"],
            },
        ),
        migrations.AddConstraint(
            model_name="sallemodel",
            constraint=models.UniqueConstraint(
                fields=("point_vente", "code"),
                name="unique_salle_code_par_restaurant",
            ),
        ),
        migrations.AddField(
            model_name="tablemodel",
            name="salle",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="tables",
                to="restaurant.sallemodel",
            ),
        ),
        migrations.AddField(
            model_name="tablemodel",
            name="actif",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="tablemodel",
            name="serveur_actuel",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="tables_restaurant_actuelles",
                to="rh.employe",
            ),
        ),
        migrations.AlterField(
            model_name="tablemodel",
            name="capacite",
            field=models.PositiveSmallIntegerField(),
        ),
        migrations.AlterField(
            model_name="tablemodel",
            name="nombre_couverts",
            field=models.PositiveSmallIntegerField(default=0),
        ),
        migrations.AlterField(
            model_name="tablemodel",
            name="statut",
            field=models.CharField(
                choices=[
                    ("LIBRE", "Libre"),
                    ("OCCUPEE", "Occupée"),
                    ("COMMANDE_EN_COURS", "Commande en cours"),
                    ("A_ENCAISSER", "À encaisser"),
                    ("RESERVEE", "Réservée"),
                    ("EN_ATTENTE", "En attente"),
                    ("HORS_SERVICE", "Hors service"),
                ],
                default="LIBRE",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="fileattentemodel",
            name="table",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="placements_file_attente",
                to="restaurant.tablemodel",
            ),
        ),
        migrations.RunPython(
            backfill_single_restaurant_room,
            reverse_code=migrations.RunPython.noop,
        ),
    ]

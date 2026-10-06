from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0006_commande_journee_exploitation_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="affectationpointvente",
            name="mode_acces",
            field=models.CharField(
                choices=[
                    ("TOTAL", "Accès total"),
                    ("PERMANENT", "Accès permanent"),
                    ("HORAIRES", "Accès selon horaires"),
                    ("PLANNING", "Accès selon planning"),
                ],
                default="PERMANENT",
                help_text=(
                    "TOTAL=tous les Bar/Restaurant ; PERMANENT=ce point de vente ; "
                    "HORAIRES=créneaux hebdomadaires ; PLANNING=shift actif obligatoire."
                ),
                max_length=20,
            ),
        ),
        migrations.CreateModel(
            name="HoraireAffectation",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("jour_semaine", models.PositiveSmallIntegerField(choices=[
                    (0, "Lundi"), (1, "Mardi"), (2, "Mercredi"), (3, "Jeudi"),
                    (4, "Vendredi"), (5, "Samedi"), (6, "Dimanche"),
                ])),
                ("heure_debut", models.TimeField()),
                ("heure_fin", models.TimeField()),
                ("date_debut", models.DateField(blank=True, null=True)),
                ("date_fin", models.DateField(blank=True, null=True)),
                ("actif", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("affectation", models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name="horaires",
                    to="pos.affectationpointvente",
                )),
            ],
            options={
                "verbose_name": "Horaire d'affectation POS",
                "verbose_name_plural": "Horaires d'affectation POS",
                "db_table": "pos_horaires_affectation",
                "ordering": ["affectation_id", "jour_semaine", "heure_debut"],
            },
        ),
        migrations.AddConstraint(
            model_name="horaireaffectation",
            constraint=models.UniqueConstraint(
                fields=("affectation", "jour_semaine", "heure_debut", "heure_fin"),
                name="unique_horaire_pos_affectation",
            ),
        ),
    ]

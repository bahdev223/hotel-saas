from django.db import migrations, models
import django.db.models


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0009_horaire_debut_fin_differents"),
    ]

    operations = [
        migrations.AddField(
            model_name="pointvente",
            name="delai_passation_minutes",
            field=models.PositiveSmallIntegerField(
                default=15,
                help_text="Délai de grâce avant comptage lors d'une passation de caisse.",
            ),
        ),
        migrations.AlterField(
            model_name="sessioncaisse",
            name="statut",
            field=models.CharField(
                choices=[
                    ("OUVERTE", "Ouverte"),
                    ("EN_PASSATION", "En passation"),
                    ("EN_COMPTAGE", "En comptage"),
                    ("FERMEE", "Fermée"),
                    ("VALIDEE", "Validée"),
                    ("ANNULEE", "Annulée"),
                ],
                default="OUVERTE",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="date_passation",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="passation_jusqua",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="date_validation",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="mode_acces_ouverture",
            field=models.CharField(
                blank=True,
                choices=[
                    ("TOTAL", "Accès total"),
                    ("PERMANENT", "Accès permanent"),
                    ("HORAIRES", "Accès selon horaires"),
                    ("PLANNING", "Accès selon planning"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="raison_acces_ouverture",
            field=models.CharField(blank=True, max_length=80),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="affectation_ouverture_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="shift_ouverture_id",
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="acces_expire_le",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="permissions_ouverture",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="sessioncaisse",
            name="motif_passation",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="comptagesession",
            name="ecart_carte",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="comptagesession",
            name="ecart_mobile",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="comptagesession",
            name="ecart_cheque",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name="comptagesession",
            name="ecart_total",
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.RemoveConstraint(
            model_name="sessioncaisse",
            name="unique_session_active_par_caisse",
        ),
        migrations.AddConstraint(
            model_name="sessioncaisse",
            constraint=models.UniqueConstraint(
                fields=("caisse",),
                condition=django.db.models.Q(
                    statut__in=["OUVERTE", "EN_PASSATION", "EN_COMPTAGE"]
                ),
                name="unique_session_active_par_caisse",
            ),
        ),
    ]

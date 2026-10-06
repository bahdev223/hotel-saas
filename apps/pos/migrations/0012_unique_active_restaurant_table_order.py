from django.db import migrations, models
import django.db.models


def assert_no_duplicate_active_table_orders(apps, schema_editor):
    from django.db.models import Count

    Commande = apps.get_model("pos", "Commande")
    active = ["EN_ATTENTE", "EN_PREPARATION", "PRETE", "SERVIE"]

    duplicates = list(
        Commande.objects
        .filter(table__isnull=False, statut__in=active)
        .values("table_id")
        .annotate(total=models.Count("id"))
        .filter(total__gt=1)
        .order_by("table_id")
    )
    if not duplicates:
        return

    details = []
    for duplicate in duplicates[:20]:
        ids = list(
            Commande.objects
            .filter(
                table_id=duplicate["table_id"],
                statut__in=active,
            )
            .order_by("created_at", "id")
            .values_list("id", flat=True)
        )
        details.append(
            f"table={duplicate['table_id']} commandes={ids}"
        )

    raise RuntimeError(
        "Impossible d'appliquer unique_active_order_per_table : "
        "des tables possèdent plusieurs commandes actives. "
        "Corrigez explicitement ces commandes avant de relancer la migration. "
        + "; ".join(details)
    )


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0011_restaurant_operational_permissions"),
        ("restaurant", "0012_waiting_list_and_table_number_scope"),
    ]

    operations = [
        migrations.RunPython(
            assert_no_duplicate_active_table_orders,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AddIndex(
            model_name="commande",
            index=models.Index(
                fields=["table", "statut"],
                name="pos_cmd_table_stat_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="commande",
            constraint=models.UniqueConstraint(
                fields=("table",),
                condition=django.db.models.Q(
                    ("table__isnull", False),
                    (
                        "statut__in",
                        ["EN_ATTENTE", "EN_PREPARATION", "PRETE", "SERVIE"],
                    ),
                ),
                name="unique_active_order_per_table",
            ),
        ),
    ]

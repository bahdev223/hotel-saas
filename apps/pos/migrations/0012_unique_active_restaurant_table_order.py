from django.db import migrations, models
import django.db.models


def resolve_duplicate_active_table_orders(apps, schema_editor):
    Commande = apps.get_model("pos", "Commande")
    active = ["EN_ATTENTE", "EN_PREPARATION", "PRETE", "SERVIE"]

    table_ids = (
        Commande.objects
        .filter(table__isnull=False, statut__in=active)
        .values_list("table_id", flat=True)
        .distinct()
    )
    for table_id in table_ids:
        orders = list(
            Commande.objects
            .filter(table_id=table_id, statut__in=active)
            .order_by("created_at", "id")
        )
        if len(orders) <= 1:
            continue
        # Préserver la commande la plus ancienne comme commande active.
        # Les doublons historiques sont annulés pour permettre la contrainte.
        Commande.objects.filter(
            id__in=[order.id for order in orders[1:]]
        ).update(statut="ANNULEE")


class Migration(migrations.Migration):
    dependencies = [
        ("pos", "0011_restaurant_operational_permissions"),
        ("restaurant", "0012_waiting_list_and_table_number_scope"),
    ]

    operations = [
        migrations.RunPython(
            resolve_duplicate_active_table_orders,
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

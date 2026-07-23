from django.db import migrations


def create_missing_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())

    for model_name in ("UniteModel", "LocationModel"):
        model = apps.get_model("hotel", model_name)
        if model._meta.db_table not in existing_tables:
            schema_editor.create_model(model)
            existing_tables.add(model._meta.db_table)


def drop_repair_tables(apps, schema_editor):
    existing_tables = set(schema_editor.connection.introspection.table_names())

    for model_name in ("LocationModel", "UniteModel"):
        model = apps.get_model("hotel", model_name)
        if model._meta.db_table in existing_tables:
            schema_editor.delete_model(model)
            existing_tables.remove(model._meta.db_table)


class Migration(migrations.Migration):

    dependencies = [
        ("hotel", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(create_missing_tables, drop_repair_tables),
    ]

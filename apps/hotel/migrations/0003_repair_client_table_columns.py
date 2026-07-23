from django.db import migrations


def add_missing_client_columns(apps, schema_editor):
    table_name = "hotel_clients"
    existing_columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    ClientModel = apps.get_model("hotel", "ClientModel")

    for field_name in ("sexe", "date_naissance", "piece_identite", "numero_piece", "actif"):
        field = ClientModel._meta.get_field(field_name)
        if field.column not in existing_columns:
            schema_editor.add_field(ClientModel, field)
            existing_columns.add(field.column)


def remove_repair_client_columns(apps, schema_editor):
    table_name = "hotel_clients"
    existing_columns = {
        column.name
        for column in schema_editor.connection.introspection.get_table_description(
            schema_editor.connection.cursor(),
            table_name,
        )
    }
    ClientModel = apps.get_model("hotel", "ClientModel")

    for field_name in ("actif", "numero_piece", "piece_identite", "date_naissance", "sexe"):
        field = ClientModel._meta.get_field(field_name)
        if field.column in existing_columns:
            schema_editor.remove_field(ClientModel, field)
            existing_columns.remove(field.column)


class Migration(migrations.Migration):

    dependencies = [
        ("hotel", "0002_create_missing_unite_location_tables"),
    ]

    operations = [
        migrations.RunPython(add_missing_client_columns, remove_repair_client_columns),
    ]

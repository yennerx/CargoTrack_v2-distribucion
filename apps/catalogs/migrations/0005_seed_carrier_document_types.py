from django.db import migrations


CARRIER_DOCUMENT_TYPES = (
    ("licencia", "Licencia", 30),
    ("seguro", "Seguro", 40),
    ("tarjeta-de-circulacion", "Tarjeta de circulación", 50),
    ("permiso", "Permiso", 60),
)


def seed_carrier_document_types(apps, schema_editor):
    entry_model = apps.get_model("catalogs", "CatalogEntry")
    for code, name, sort_order in CARRIER_DOCUMENT_TYPES:
        entry_model.objects.update_or_create(
            catalog_type="document_type",
            code=code,
            defaults={
                "name": name,
                "sort_order": sort_order,
                "is_active": True,
                "is_system_defined": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0004_rename_catalog_index")]

    operations = [
        migrations.RunPython(seed_carrier_document_types, migrations.RunPython.noop),
    ]

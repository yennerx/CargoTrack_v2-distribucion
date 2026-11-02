from django.db import migrations


DOCUMENT_TYPES = (
    ("constancia-entrega", "Constancia de entrega", 30),
    ("comprobante-cobro", "Comprobante de cobro", 40),
    ("comprobante-gasto", "Comprobante de gasto", 50),
)


def seed_closing_document_types(apps, schema_editor):
    entry_model = apps.get_model("catalogs", "CatalogEntry")
    for code, name, sort_order in DOCUMENT_TYPES:
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
    dependencies = [("catalogs", "0009_disable_order_tax_movement")]
    operations = [migrations.RunPython(seed_closing_document_types, migrations.RunPython.noop)]

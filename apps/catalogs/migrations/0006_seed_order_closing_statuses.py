from django.db import migrations


ORDER_CLOSING_STATUSES = (
    ("pendiente-cierre", "Pendiente de cierre", 100),
    ("cerrada", "Cerrada", 110),
    ("reabierta", "Reabierta", 120),
)


def seed_order_closing_statuses(apps, schema_editor):
    catalog_entry = apps.get_model("catalogs", "CatalogEntry")
    for code, name, sort_order in ORDER_CLOSING_STATUSES:
        catalog_entry.objects.update_or_create(
            catalog_type="order_status",
            code=code,
            defaults={
                "name": name,
                "sort_order": sort_order,
                "is_active": True,
                "is_system_defined": True,
            },
        )


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0005_seed_carrier_document_types")]

    operations = [migrations.RunPython(seed_order_closing_statuses, migrations.RunPython.noop)]

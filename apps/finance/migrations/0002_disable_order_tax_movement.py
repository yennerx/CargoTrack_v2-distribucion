from django.db import migrations


def disable_order_tax_movement(apps, schema_editor):
    entry_model = apps.get_model("catalogs", "CatalogEntry")
    entry_model.objects.filter(catalog_type="financial_movement", code="impuesto").update(
        is_active=False
    )


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0009_disable_order_tax_movement"),
        ("finance", "0001_initial"),
    ]
    operations = [migrations.RunPython(disable_order_tax_movement, migrations.RunPython.noop)]

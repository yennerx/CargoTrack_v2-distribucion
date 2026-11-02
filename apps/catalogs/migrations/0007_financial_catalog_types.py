from django.db import migrations


def seed_financial_catalogs(apps, schema_editor):
    entry_model = apps.get_model("catalogs", "CatalogEntry")
    values = {
        "currency": (("usd", "Dólar estadounidense", 10),),
        "cost_type": (
            ("costo-transportista", "Costo de transportista", 10),
            ("asistencia-carga-descarga", "Asistencia para carga o descarga", 20),
            ("almacenaje", "Almacenaje", 30),
            ("otro-costo", "Otro costo", 40),
        ),
    }
    for catalog_type, entries in values.items():
        for code, name, sort_order in entries:
            entry_model.objects.update_or_create(
                catalog_type=catalog_type,
                code=code,
                defaults={"name": name, "sort_order": sort_order, "is_system_defined": True},
            )


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0006_seed_order_closing_statuses")]
    operations = [migrations.RunPython(seed_financial_catalogs, migrations.RunPython.noop)]

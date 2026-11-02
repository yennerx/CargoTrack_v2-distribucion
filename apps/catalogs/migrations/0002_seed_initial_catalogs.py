from django.db import migrations


ORDER_STATUSES = (
    ("solicitud-recibida", "Solicitud recibida", 10),
    ("en-negociacion", "En negociación", 20),
    ("pendiente-documentacion", "Pendiente de documentación", 30),
    ("validada", "Validada", 40),
    ("asignada", "Asignada", 50),
    ("en-recogida", "En recogida", 60),
    ("en-transito", "En tránsito", 70),
    ("entregada", "Entregada", 80),
    ("cancelada", "Cancelada", 90),
)

DOCUMENT_TYPES = (
    ("factura", "Factura", 10),
    ("recibo", "Recibo", 20),
)

FINANCIAL_MOVEMENTS = (
    ("cobro-cliente", "Cobro al cliente", 10),
    ("pago-transportista", "Pago al transportista", 20),
    ("impuesto", "Impuesto", 30),
    ("gasto-transporte", "Gasto de transporte", 40),
    ("otro-gasto", "Otro gasto", 50),
)


def seed_catalogs(apps, schema_editor):
    entry_model = apps.get_model("catalogs", "CatalogEntry")
    configuration_model = apps.get_model("catalogs", "SystemConfiguration")

    entries = (
        ("order_status", ORDER_STATUSES),
        ("document_type", DOCUMENT_TYPES),
        ("financial_movement", FINANCIAL_MOVEMENTS),
    )
    for catalog_type, values in entries:
        for code, name, sort_order in values:
            entry_model.objects.update_or_create(
                catalog_type=catalog_type,
                code=code,
                defaults={
                    "name": name,
                    "sort_order": sort_order,
                    "is_active": True,
                    "is_system_defined": True,
                },
            )

    configuration_model.objects.update_or_create(
        key="operating-currency",
        defaults={
            "value": "USD",
            "description": "Moneda operativa inicial del sistema",
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0001_initial")]

    operations = [migrations.RunPython(seed_catalogs, migrations.RunPython.noop)]

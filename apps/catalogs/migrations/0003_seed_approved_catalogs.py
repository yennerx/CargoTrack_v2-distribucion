from django.db import migrations, models


APPROVED_CATALOGS = (
    (
        "cargo_type",
        (
            ("carga-seca", "Carga seca", 10),
            ("carga-refrigerada-congelada", "Carga refrigerada / congelada", 20),
            ("carga-sobredimensionada", "Carga sobredimensionada", 30),
            ("carga-peligrosa", "Carga peligrosa (HazMat)", 40),
            ("carga-granel", "Carga de granel", 50),
            ("carga-fragil", "Carga frágil", 60),
            ("carga-alto-valor", "Carga de alto valor", 70),
        ),
    ),
    (
        "equipment_type",
        (
            ("tractocamion", "Tractocamión", 10),
            ("remolque-semirremolque", "Remolque / semirremolque", 20),
            ("contenedor-dry-van", "Contenedor (Dry Van)", 30),
            ("unidad-de-carga", "Unidad de carga (Box Truck)", 40),
            ("plataforma", "Plataforma / camión de plataforma", 50),
            ("cisterna", "Cisterna", 60),
            ("remolque-refrigerado", "Remolque refrigerado", 70),
        ),
    ),
    (
        "incident_type",
        (
            ("dano-en-mercancia", "Daño en mercancía", 10),
            ("retraso-en-entrega", "Retraso en entrega", 20),
            ("falla-mecanica", "Falla mecánica", 30),
            ("accidente-de-transito", "Accidente de tránsito", 40),
            ("robo-sustraccion", "Robo / sustracción", 50),
            ("documentacion-faltante", "Documentación faltante", 60),
            ("rechazo-en-destino", "Rechazo en destino", 70),
        ),
    ),
    (
        "incident_priority",
        (
            ("critica", "Crítica", 10),
            ("alta", "Alta", 20),
            ("media", "Media", 30),
            ("baja", "Baja", 40),
        ),
    ),
    (
        "expense_type",
        (
            ("combustible", "Combustible", 10),
            ("peajes", "Peajes", 20),
            ("mantenimiento", "Mantenimiento", 30),
            ("viaticos-alojamiento", "Viáticos / alojamiento", 40),
            ("multas", "Multas", 50),
            ("carga-y-descarga", "Carga y descarga", 60),
            ("seguros", "Seguros", 70),
        ),
    ),
)


def seed_approved_catalogs(apps, schema_editor):
    entry_model = apps.get_model("catalogs", "CatalogEntry")

    for catalog_type, values in APPROVED_CATALOGS:
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


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0002_seed_initial_catalogs")]

    operations = [
        migrations.AlterField(
            model_name="catalogentry",
            name="catalog_type",
            field=models.CharField(
                choices=[
                    ("order_status", "Estado operativo"),
                    ("document_type", "Tipo documental"),
                    ("cargo_type", "Tipo de carga"),
                    ("equipment_type", "Tipo de equipo"),
                    ("incident_type", "Tipo de incidencia"),
                    ("incident_priority", "Prioridad de incidencia"),
                    ("financial_movement", "Movimiento financiero"),
                    ("expense_type", "Tipo de gasto"),
                ],
                max_length=40,
            ),
        ),
        migrations.RunPython(seed_approved_catalogs, migrations.RunPython.noop),
    ]

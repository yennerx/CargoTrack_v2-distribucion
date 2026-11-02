from django.db import migrations


def seed_report_configuration(apps, schema_editor):
    configuration_model = apps.get_model("catalogs", "SystemConfiguration")
    configuration_model.objects.update_or_create(
        key="report-page-size",
        defaults={
            "value": "25",
            "description": "Filas por página para reportes",
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0010_seed_closing_document_types")]
    operations = [migrations.RunPython(seed_report_configuration, migrations.RunPython.noop)]

from django.db import migrations


def seed_session_idle_timeout(apps, schema_editor):
    configuration_model = apps.get_model("catalogs", "SystemConfiguration")
    configuration_model.objects.update_or_create(
        key="session-idle-timeout-minutes",
        defaults={
            "value": "5",
            "description": "Minutos de inactividad antes de cerrar una sesión",
            "is_active": True,
        },
    )


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0011_seed_report_configuration")]

    operations = [
        migrations.RunPython(seed_session_idle_timeout, migrations.RunPython.noop)
    ]

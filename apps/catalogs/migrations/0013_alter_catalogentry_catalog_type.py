import django.db.models
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("catalogs", "0012_seed_session_idle_timeout")]

    operations = [
        migrations.AlterField(
            model_name="catalogentry",
            name="catalog_type",
            field=django.db.models.CharField(
                choices=[
                    ("order_status", "Estados de orden"),
                    ("document_type", "Tipo documental"),
                    ("cargo_type", "Tipo de carga"),
                    ("equipment_type", "Tipo de equipo"),
                    ("incident_type", "Tipo de incidencia"),
                    ("incident_priority", "Prioridad de incidencia"),
                    ("financial_movement", "Movimiento financiero"),
                    ("expense_type", "Tipo de gasto"),
                    ("currency", "Moneda"),
                    ("cost_type", "Tipo de costo"),
                ],
                max_length=40,
            ),
        )
    ]

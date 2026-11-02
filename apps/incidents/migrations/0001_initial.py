import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogs", "0006_seed_order_closing_statuses"),
        ("orders", "0003_orderstatushistory"),
    ]

    operations = [
        migrations.CreateModel(
            name="Incident",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("open", "Abierta"), ("in_progress", "En seguimiento"), ("resolved", "Resuelta"), ("closed", "Cerrada"), ("reopened", "Reabierta")], default="open", max_length=20)),
                ("title", models.CharField(max_length=200)),
                ("description", models.TextField()),
                ("resolution", models.TextField(blank=True)),
                ("resolved_at", models.DateTimeField(blank=True, null=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("assigned_to", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="assigned_incidents", to=settings.AUTH_USER_MODEL)),
                ("closed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="closed_incidents", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_incidents", to=settings.AUTH_USER_MODEL)),
                ("incident_type", models.ForeignKey(limit_choices_to={"catalog_type": "incident_type"}, on_delete=django.db.models.deletion.PROTECT, related_name="incidents", to="catalogs.catalogentry")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incidents", to="orders.order")),
                ("priority", models.ForeignKey(limit_choices_to={"catalog_type": "incident_priority"}, on_delete=django.db.models.deletion.PROTECT, related_name="priority_incidents", to="catalogs.catalogentry")),
                ("resolved_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="resolved_incidents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.CreateModel(
            name="IncidentHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("previous_status", models.CharField(blank=True, choices=[("open", "Abierta"), ("in_progress", "En seguimiento"), ("resolved", "Resuelta"), ("closed", "Cerrada"), ("reopened", "Reabierta")], max_length=20)),
                ("status", models.CharField(choices=[("open", "Abierta"), ("in_progress", "En seguimiento"), ("resolved", "Resuelta"), ("closed", "Cerrada"), ("reopened", "Reabierta")], max_length=20)),
                ("observation", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                ("changed_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="incident_history_changes", to=settings.AUTH_USER_MODEL)),
                ("incident", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="history", to="incidents.incident")),
            ],
            options={"ordering": ("-changed_at",)},
        ),
        migrations.AddIndex(model_name="incident", index=models.Index(fields=("order", "status"), name="incidents_i_order_i_5b7e9f_idx")),
        migrations.AddIndex(model_name="incident", index=models.Index(fields=("priority", "status"), name="incidents_i_priorit_2ecaa6_idx")),
    ]

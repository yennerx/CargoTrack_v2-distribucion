from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("carriers", "0002_carrier_related_timestamps"),
        ("catalogs", "0005_seed_carrier_document_types"),
        ("customers", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderNumberSequence",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("year", models.PositiveIntegerField(unique=True)),
                ("last_number", models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("number", models.CharField(blank=True, max_length=20, unique=True)),
                ("origin", models.CharField(max_length=255)),
                ("destination", models.CharField(max_length=255)),
                ("pickup_date", models.DateField()),
                ("delivery_date", models.DateField()),
                ("customer_rate", models.DecimalField(decimal_places=2, max_digits=12)),
                ("carrier_cost", models.DecimalField(decimal_places=2, max_digits=12)),
                ("rate_conditions", models.TextField(blank=True)),
                ("logistics_notes", models.TextField(blank=True)),
                ("proposed_at", models.DateTimeField(blank=True, null=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("formalized_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("broker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="broker_orders", to=settings.AUTH_USER_MODEL)),
                ("cargo_type", models.ForeignKey(limit_choices_to={"catalog_type": "cargo_type"}, on_delete=django.db.models.deletion.PROTECT, related_name="cargo_orders", to="catalogs.catalogentry")),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_orders", to=settings.AUTH_USER_MODEL)),
                ("confirmed_carrier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="confirmed_orders", to="carriers.carrier")),
                ("customer", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="customers.customer")),
                ("dispatcher", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="dispatcher_orders", to=settings.AUTH_USER_MODEL)),
                ("equipment_type", models.ForeignKey(limit_choices_to={"catalog_type": "equipment_type"}, on_delete=django.db.models.deletion.PROTECT, related_name="equipment_orders", to="catalogs.catalogentry")),
                ("formalized_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="formalized_orders", to=settings.AUTH_USER_MODEL)),
                ("proposed_carrier", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="proposed_orders", to="carriers.carrier")),
                ("status", models.ForeignKey(limit_choices_to={"catalog_type": "order_status"}, on_delete=django.db.models.deletion.PROTECT, related_name="orders", to="catalogs.catalogentry")),
            ],
            options={"ordering": ("-created_at",)},
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["status", "created_at"], name="orders_orde_status_0f98f8_idx"),
        ),
        migrations.AddIndex(
            model_name="order",
            index=models.Index(fields=["customer", "created_at"], name="orders_orde_custome_3bc7a6_idx"),
        ),
    ]

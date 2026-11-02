from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogs", "0005_seed_carrier_document_types"),
    ]

    operations = [
        migrations.CreateModel(
            name="Carrier",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("carrier_type", models.CharField(choices=[("person", "Persona individual"), ("company", "Empresa")], max_length=20)),
                ("nit", models.CharField(db_index=True, max_length=30, unique=True)),
                ("legal_name", models.CharField(max_length=200)),
                ("commercial_name", models.CharField(blank=True, max_length=200)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("primary_phone", models.CharField(max_length=40)),
                ("email", models.EmailField(max_length=254)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("is_validated", models.BooleanField(default=False)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_carriers", to=settings.AUTH_USER_MODEL)),
                ("validated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="validated_carriers", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "ordering": ("legal_name", "nit"),
                "constraints": [models.CheckConstraint(condition=~models.Q(nit=""), name="carrier_nit_not_blank")],
            },
        ),
        migrations.CreateModel(
            name="CarrierDocument",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("document_number", models.CharField(max_length=100)),
                ("issued_at", models.DateField(blank=True, null=True)),
                ("expires_at", models.DateField()),
                ("notes", models.TextField(blank=True)),
                ("is_validated", models.BooleanField(default=False)),
                ("validated_at", models.DateTimeField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("carrier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="documents", to="carriers.carrier")),
                ("document_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="carrier_documents", to="catalogs.catalogentry")),
                ("validated_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="validated_carrier_documents", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("expires_at", "document_type")},
        ),
        migrations.CreateModel(
            name="CarrierUnit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("unit_identifier", models.CharField(max_length=80)),
                ("license_plate", models.CharField(max_length=30)),
                ("brand", models.CharField(blank=True, max_length=80)),
                ("model", models.CharField(blank=True, max_length=80)),
                ("is_active", models.BooleanField(default=True)),
                ("carrier", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="units", to="carriers.carrier")),
                ("equipment_type", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="carrier_units", to="catalogs.catalogentry")),
            ],
            options={
                "ordering": ("unit_identifier",),
                "constraints": [
                    models.UniqueConstraint(fields=("carrier", "unit_identifier"), name="unique_carrier_unit_identifier"),
                    models.UniqueConstraint(condition=models.Q(is_active=True), fields=("license_plate",), name="unique_active_license_plate"),
                ],
            },
        ),
    ]

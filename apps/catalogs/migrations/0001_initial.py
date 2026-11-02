from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    operations = [
        migrations.CreateModel(
            name="CatalogEntry",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "catalog_type",
                    models.CharField(
                        choices=[
                            ("order_status", "Estado operativo"),
                            ("document_type", "Tipo documental"),
                            ("incident_type", "Tipo de incidencia"),
                            ("incident_priority", "Prioridad de incidencia"),
                            ("financial_movement", "Movimiento financiero"),
                            ("expense_type", "Tipo de gasto"),
                        ],
                        max_length=40,
                    ),
                ),
                ("code", models.SlugField(max_length=60)),
                ("name", models.CharField(max_length=120)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("sort_order", models.PositiveIntegerField(default=0)),
                ("is_active", models.BooleanField(default=True)),
                ("is_system_defined", models.BooleanField(default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("catalog_type", "sort_order", "name")},
        ),
        migrations.CreateModel(
            name="SystemConfiguration",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("key", models.SlugField(max_length=80, unique=True)),
                ("value", models.CharField(max_length=255)),
                ("description", models.CharField(blank=True, max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ("key",)},
        ),
        migrations.AddConstraint(
            model_name="catalogentry",
            constraint=models.UniqueConstraint(
                fields=("catalog_type", "code"),
                name="unique_catalog_type_code",
            ),
        ),
        migrations.AddIndex(
            model_name="catalogentry",
            index=models.Index(fields=["catalog_type", "is_active"], name="catalogs_ca_catalog_8b8b16_idx"),
        ),
    ]

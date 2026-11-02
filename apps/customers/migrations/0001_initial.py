from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True

    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="Customer",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nit", models.CharField(db_index=True, max_length=30, unique=True)),
                ("legal_name", models.CharField(max_length=200)),
                ("commercial_name", models.CharField(blank=True, max_length=200)),
                ("address", models.CharField(blank=True, max_length=255)),
                ("city", models.CharField(blank=True, max_length=100)),
                ("country", models.CharField(blank=True, max_length=100)),
                ("notes", models.TextField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "created_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="created_customers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ("legal_name", "nit"),
                "constraints": [
                    models.CheckConstraint(
                        condition=~models.Q(nit=""),
                        name="customer_nit_not_blank",
                    ),
                ],
                "indexes": [models.Index(fields=("is_active", "legal_name"), name="customers_c_is_acti_bc6029_idx")],
            },
        ),
        migrations.CreateModel(
            name="CustomerContact",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=150)),
                ("position", models.CharField(blank=True, max_length=120)),
                ("primary_phone", models.CharField(max_length=40)),
                ("secondary_phone", models.CharField(blank=True, max_length=40)),
                ("email", models.EmailField(max_length=254)),
                ("preferred_contact_method", models.CharField(blank=True, max_length=30)),
                ("is_primary", models.BooleanField(default=False)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "customer",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="contacts",
                        to="customers.customer",
                    ),
                ),
            ],
            options={
                "ordering": ("-is_primary", "name"),
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(is_active=True, is_primary=True),
                        fields=("customer",),
                        name="one_active_primary_contact",
                    )
                ],
            },
        ),
    ]

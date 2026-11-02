from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogs", "0005_seed_carrier_document_types"),
        ("orders", "0002_rename_orders_orde_status_0f98f8_idx_orders_orde_status__ea94e1_idx_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="OrderStatusHistory",
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
                ("observation", models.TextField(blank=True)),
                ("changed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "changed_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="order_status_changes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="status_history",
                        to="orders.order",
                    ),
                ),
                (
                    "previous_status",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="previous_order_status_history",
                        to="catalogs.catalogentry",
                    ),
                ),
                (
                    "status",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="order_status_history",
                        to="catalogs.catalogentry",
                    ),
                ),
            ],
            options={"ordering": ("-changed_at",)},
        ),
    ]

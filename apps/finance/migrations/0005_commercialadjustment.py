import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0004_commissions"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommercialAdjustment",
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
                    "target",
                    models.CharField(
                        choices=[("customer", "Cliente"), ("carrier", "Transportista")],
                        max_length=20,
                    ),
                ),
                ("amount_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("reason", models.TextField()),
                ("reference", models.CharField(blank=True, max_length=120)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pendiente de aprobación"),
                            ("approved", "Aprobado"),
                            ("rejected", "Rechazado"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("requested_at", models.DateTimeField(auto_now_add=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("review_observation", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "order",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="commercial_adjustments",
                        to="orders.order",
                    ),
                ),
                (
                    "requested_by",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="requested_commercial_adjustments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "reviewed_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="reviewed_commercial_adjustments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={"ordering": ("-requested_at",)},
        ),
        migrations.AddConstraint(
            model_name="commercialadjustment",
            constraint=models.CheckConstraint(
                condition=~models.Q(amount_usd=0), name="commercial_adjustment_nonzero"
            ),
        ),
        migrations.AddIndex(
            model_name="commercialadjustment",
            index=models.Index(fields=["order", "status"], name="finance_com_order_9c62d4_idx"),
        ),
        migrations.AddIndex(
            model_name="commercialadjustment",
            index=models.Index(fields=["target", "status"], name="finance_com_target_42e52e_idx"),
        ),
    ]

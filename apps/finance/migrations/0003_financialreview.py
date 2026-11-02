import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0002_disable_order_tax_movement"),
        ("orders", "0003_orderstatushistory"),
    ]
    operations = [
        migrations.CreateModel(
            name="FinancialReview",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("validated", "Validado"), ("rejected", "Rechazado")], default="pending", max_length=20)),
                ("observation", models.TextField(blank=True)),
                ("reviewed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="financial_review", to="orders.order")),
                ("reviewed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="financial_reviews", to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]

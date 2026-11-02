import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("catalogs", "0008_alter_catalogentry_catalog_type"),
        ("orders", "0003_orderstatushistory"),
    ]
    operations = [
        migrations.CreateModel(
            name="FinancialTransaction",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14)),
                ("exchange_rate_to_usd", models.DecimalField(decimal_places=6, default=1, max_digits=14)),
                ("base_amount_usd", models.DecimalField(blank=True, decimal_places=2, max_digits=14)),
                ("status", models.CharField(choices=[("pending", "Pendiente"), ("confirmed", "Confirmado"), ("voided", "Anulado")], default="pending", max_length=20)),
                ("transaction_date", models.DateField()),
                ("reference", models.CharField(blank=True, max_length=120)),
                ("description", models.TextField(blank=True)),
                ("confirmed_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("adjustment_of", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="adjustments", to="finance.financialtransaction")),
                ("confirmed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="confirmed_financial_transactions", to=settings.AUTH_USER_MODEL)),
                ("cost_type", models.ForeignKey(blank=True, limit_choices_to={"catalog_type": "cost_type"}, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cost_transactions", to="catalogs.catalogentry")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_financial_transactions", to=settings.AUTH_USER_MODEL)),
                ("currency", models.ForeignKey(limit_choices_to={"catalog_type": "currency"}, on_delete=django.db.models.deletion.PROTECT, related_name="financial_transactions_currency", to="catalogs.catalogentry")),
                ("movement_type", models.ForeignKey(limit_choices_to={"catalog_type": "financial_movement"}, on_delete=django.db.models.deletion.PROTECT, related_name="financial_transactions", to="catalogs.catalogentry")),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="financial_transactions", to="orders.order")),
            ],
            options={"ordering": ("-transaction_date", "-created_at")},
        ),
    ]

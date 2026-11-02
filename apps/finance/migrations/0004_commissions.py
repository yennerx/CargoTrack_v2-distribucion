import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("finance", "0003_financialreview"),
    ]

    operations = [
        migrations.CreateModel(
            name="CommissionRule",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("percentage", models.DecimalField(decimal_places=2, max_digits=5)),
                ("valid_from", models.DateField()),
                ("valid_to", models.DateField(blank=True, null=True)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("broker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commission_rules", to=settings.AUTH_USER_MODEL)),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="created_commission_rules", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ("broker", "-valid_from", "-created_at")},
        ),
        migrations.CreateModel(
            name="Commission",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gross_profit_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("commission_rate", models.DecimalField(decimal_places=2, max_digits=5)),
                ("gross_commission_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("customer_unpaid_discount_usd", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("commission_amount_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("loss_amount_usd", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("company_covered_loss_usd", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("agreed_broker_debt_usd", models.DecimalField(decimal_places=2, default=0, max_digits=14)),
                ("status", models.CharField(choices=[("calculated", "Calculada"), ("authorized", "Autorizada"), ("paid", "Pagada"), ("voided", "Anulada")], default="calculated", max_length=20)),
                ("loss_report", models.TextField(blank=True)),
                ("negotiation_agreement", models.TextField(blank=True)),
                ("calculated_at", models.DateTimeField(auto_now_add=True)),
                ("authorized_at", models.DateTimeField(blank=True, null=True)),
                ("paid_at", models.DateTimeField(blank=True, null=True)),
                ("payment_method", models.CharField(blank=True, max_length=40)),
                ("payment_reference", models.CharField(blank=True, max_length=120)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("authorized_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="authorized_commissions", to=settings.AUTH_USER_MODEL)),
                ("broker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commissions", to=settings.AUTH_USER_MODEL)),
                ("calculated_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="calculated_commissions", to=settings.AUTH_USER_MODEL)),
                ("order", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="commission", to="orders.order")),
                ("paid_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="paid_commissions", to=settings.AUTH_USER_MODEL)),
                ("rule", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commissions", to="finance.commissionrule")),
            ],
            options={"ordering": ("-calculated_at",)},
        ),
        migrations.CreateModel(
            name="BrokerDebt",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("loss_report", models.TextField()),
                ("negotiation_agreement", models.TextField()),
                ("loss_amount_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("company_covered_loss_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("agreed_amount_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("balance_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("responsibility_percentage", models.DecimalField(decimal_places=2, max_digits=5)),
                ("status", models.CharField(choices=[("open", "Pendiente"), ("settled", "Saldada"), ("voided", "Anulada")], default="open", max_length=20)),
                ("approved_at", models.DateTimeField(auto_now_add=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("approved_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="approved_broker_debts", to=settings.AUTH_USER_MODEL)),
                ("broker", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="broker_debts", to=settings.AUTH_USER_MODEL)),
                ("origin_commission", models.OneToOneField(on_delete=django.db.models.deletion.PROTECT, related_name="broker_debt", to="finance.commission")),
            ],
        ),
        migrations.CreateModel(
            name="CommissionDebtApplication",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("amount_usd", models.DecimalField(decimal_places=2, max_digits=14)),
                ("applied_at", models.DateTimeField(auto_now_add=True)),
                ("applied_by", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="commission_debt_applications", to=settings.AUTH_USER_MODEL)),
                ("commission", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="debt_applications", to="finance.commission")),
                ("debt", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="applications", to="finance.brokerdebt")),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("debt", "commission"), name="unique_debt_commission_application")
                ]
            },
        ),
    ]

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def backfill_order_creator(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    Order.objects.filter(created_by__isnull=True).update(
        created_by_id=models.F("broker_id")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0003_orderstatushistory"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="created_by",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_orders",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_order_creator, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="order",
            name="created_by",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="created_orders",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]

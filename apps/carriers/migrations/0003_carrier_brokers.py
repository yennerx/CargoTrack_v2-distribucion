from django.conf import settings
from django.db import migrations, models
from django.db.models import Q


def backfill_carrier_brokers(apps, schema_editor):
    Carrier = apps.get_model("carriers", "Carrier")
    Order = apps.get_model("orders", "Order")
    Group = apps.get_model("auth", "Group")
    broker_group = Group.objects.filter(name="Broker").first()
    if broker_group is None:
        return

    broker_ids = set(broker_group.user_set.values_list("pk", flat=True))
    Assignment = Carrier.brokers.through
    for carrier in Carrier.objects.all().iterator():
        related_orders = Order.objects.filter(
            Q(proposed_carrier_id=carrier.pk) | Q(confirmed_carrier_id=carrier.pk),
            broker_id__in=broker_ids,
        )
        assigned_ids = set(related_orders.values_list("broker_id", flat=True).distinct())
        if not assigned_ids and carrier.created_by_id in broker_ids:
            assigned_ids.add(carrier.created_by_id)
        Assignment.objects.bulk_create(
            [
                Assignment(carrier_id=carrier.pk, user_id=broker_id)
                for broker_id in assigned_ids
            ],
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("carriers", "0002_carrier_related_timestamps"),
        ("orders", "0004_order_created_by"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="carrier",
            name="brokers",
            field=models.ManyToManyField(
                blank=True,
                related_name="assigned_carriers",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_carrier_brokers, migrations.RunPython.noop),
    ]

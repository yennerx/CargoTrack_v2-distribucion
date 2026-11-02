from django.conf import settings
from django.db import migrations, models


def backfill_customer_brokers(apps, schema_editor):
    Customer = apps.get_model("customers", "Customer")
    Order = apps.get_model("orders", "Order")
    Group = apps.get_model("auth", "Group")
    broker_group = Group.objects.filter(name="Broker").first()
    if broker_group is None:
        return

    broker_ids = set(broker_group.user_set.values_list("pk", flat=True))
    Assignment = Customer.brokers.through
    for customer in Customer.objects.all().iterator():
        assigned_ids = set(
            Order.objects.filter(customer_id=customer.pk, broker_id__in=broker_ids)
            .values_list("broker_id", flat=True)
            .distinct()
        )
        if not assigned_ids and customer.created_by_id in broker_ids:
            assigned_ids.add(customer.created_by_id)
        Assignment.objects.bulk_create(
            [
                Assignment(customer_id=customer.pk, user_id=broker_id)
                for broker_id in assigned_ids
            ],
            ignore_conflicts=True,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("customers", "0001_initial"),
        ("orders", "0004_order_created_by"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="customer",
            name="brokers",
            field=models.ManyToManyField(
                blank=True,
                related_name="assigned_customers",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.RunPython(backfill_customer_brokers, migrations.RunPython.noop),
    ]

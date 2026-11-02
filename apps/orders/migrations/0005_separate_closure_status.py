from django.db import migrations, models


CLOSURE_STATUS_BY_CODE = {
    "pendiente-cierre": "pending",
    "cerrada": "closed",
    "reabierta": "reopened",
}
CLOSURE_CODES = tuple(CLOSURE_STATUS_BY_CODE)


def separate_closure_status(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    OrderStatusHistory = apps.get_model("orders", "OrderStatusHistory")
    CatalogEntry = apps.get_model("catalogs", "CatalogEntry")
    database = schema_editor.connection.alias
    delivered_status = CatalogEntry.objects.using(database).get(
        catalog_type="order_status", code="entregada"
    )

    for order in Order.objects.using(database).select_related("status").iterator():
        closure_status = CLOSURE_STATUS_BY_CODE.get(order.status.code)
        if not closure_status:
            continue
        previous_operational_status = (
            OrderStatusHistory.objects.using(database)
            .filter(order_id=order.pk)
            .exclude(status__code__in=CLOSURE_CODES)
            .order_by("-changed_at", "-pk")
            .values_list("status_id", flat=True)
            .first()
        )
        # Reaching closure requires delivery, so delivered is the fallback if
        # an older record lacks its status-history rows.
        order.status_id = previous_operational_status or delivered_status.pk
        order.closure_status = closure_status
        order.save(using=database, update_fields=("status", "closure_status"))


def restore_combined_status(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    CatalogEntry = apps.get_model("catalogs", "CatalogEntry")
    database = schema_editor.connection.alias
    status_ids = {
        code: entry.pk
        for code, entry in CatalogEntry.objects.using(database)
        .filter(catalog_type="order_status", code__in=CLOSURE_CODES)
        .in_bulk(field_name="code")
        .items()
    }
    reverse_codes = {value: key for key, value in CLOSURE_STATUS_BY_CODE.items()}
    for order in Order.objects.using(database).exclude(closure_status="open").iterator():
        closure_code = reverse_codes.get(order.closure_status)
        if closure_code in status_ids:
            order.status_id = status_ids[closure_code]
            order.save(using=database, update_fields=("status",))


class Migration(migrations.Migration):
    dependencies = [
        ("catalogs", "0006_seed_order_closing_statuses"),
        ("orders", "0004_order_created_by"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="closure_status",
            field=models.CharField(
                choices=[
                    ("open", "Abierta"),
                    ("pending", "Pendiente de cierre"),
                    ("closed", "Cerrada"),
                    ("reopened", "Reabierta"),
                ],
                default="open",
                max_length=20,
            ),
        ),
        migrations.RunPython(separate_closure_status, restore_combined_status),
    ]

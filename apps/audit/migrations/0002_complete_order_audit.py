import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


REDACTED_METADATA_KEYS = {
    "amount",
    "amount_usd",
    "access_token",
    "address",
    "balance_usd",
    "broker",
    "broker_debt_usd",
    "carrier_cost",
    "carrier",
    "commission_amount_usd",
    "commission_rate",
    "company_covered_usd",
    "customer",
    "customer_rate",
    "description",
    "document_number",
    "email",
    "first_name",
    "gross_commission_usd",
    "gross_profit_usd",
    "loss_amount_usd",
    "nit",
    "last_name",
    "order_id",
    "original_name",
    "password",
    "payment_method",
    "payment_reference",
    "phone",
    "percentage",
    "reference",
    "secret",
    "stored_name",
    "token",
    "user_agent",
    "observation",
}


def redact_metadata(value):
    if isinstance(value, dict):
        return {
            key: redact_metadata(nested_value)
            for key, nested_value in value.items()
            if str(key).strip().lower() not in REDACTED_METADATA_KEYS
        }
    if isinstance(value, list):
        return [redact_metadata(item) for item in value]
    return value


def parse_identifier(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def related_order_id(event, apps, database):
    Order = apps.get_model("orders", "Order")
    order_id = parse_identifier(event.entity_id) if event.entity_type == "order" else None
    metadata = event.metadata if isinstance(event.metadata, dict) else {}
    order_id = order_id or parse_identifier(metadata.get("order_id"))

    if not order_id:
        entity_id = parse_identifier(event.entity_id)
        model_names = {
            "incident": ("incidents", "Incident", "order_id"),
            "financial_transaction": ("finance", "FinancialTransaction", "order_id"),
            "financial_review": ("finance", "FinancialReview", "order_id"),
            "commercial_adjustment": ("finance", "CommercialAdjustment", "order_id"),
            "commission": ("finance", "Commission", "order_id"),
            "broker_debt": ("finance", "BrokerDebt", "origin_commission__order_id"),
            "commission_debt_application": (
                "finance",
                "CommissionDebtApplication",
                "commission__order_id",
            ),
        }
        if event.entity_type == "document":
            document = (
                apps.get_model("documents", "Document")
                .objects.using(database)
                .filter(pk=entity_id)
                .values("order_id", "incident_id")
                .first()
            )
            if document:
                order_id = document["order_id"]
                if not order_id and document["incident_id"]:
                    order_id = (
                        apps.get_model("incidents", "Incident")
                        .objects.using(database)
                        .filter(pk=document["incident_id"])
                        .values_list("order_id", flat=True)
                        .first()
                    )
        elif event.entity_type in model_names and entity_id:
            app_label, model_name, field_name = model_names[event.entity_type]
            order_id = (
                apps.get_model(app_label, model_name)
                .objects.using(database)
                .filter(pk=entity_id)
                .values_list(field_name, flat=True)
                .first()
            )

    if order_id and Order.objects.using(database).filter(pk=order_id).exists():
        return order_id
    return None


def backfill_order_links_and_redact_metadata(apps, schema_editor):
    AuditEvent = apps.get_model("audit", "AuditEvent")
    database = schema_editor.connection.alias
    for event in AuditEvent.objects.using(database).iterator():
        order_id = related_order_id(event, apps, database)
        metadata = redact_metadata(event.metadata)
        if order_id != event.order_id or metadata != event.metadata:
            event.order_id = order_id
            event.metadata = metadata
            event.save(update_fields=("order", "metadata"))


class Migration(migrations.Migration):
    dependencies = [
        ("audit", "0001_initial"),
        ("documents", "0001_initial"),
        ("finance", "0005_commercialadjustment"),
        ("incidents", "0001_initial"),
        ("orders", "0005_separate_closure_status"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="auditevent",
            name="order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audit_events",
                to="orders.order",
            ),
        ),
        migrations.AlterField(
            model_name="auditevent",
            name="actor",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="audit_events",
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AddIndex(
            model_name="auditevent",
            index=models.Index(
                fields=("order", "created_at"), name="audit_order_created_idx"
            ),
        ),
        migrations.RunPython(
            backfill_order_links_and_redact_metadata,
            migrations.RunPython.noop,
        ),
    ]

from datetime import date
from decimal import Decimal
from importlib import import_module

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.db import connection
from django.urls import reverse

from apps.carriers.models import Carrier, CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer
from apps.orders.models import Order

from .models import AuditEvent


def create_order(user, *, number="ORD-AUDIT-001"):
    customer = Customer.objects.create(
        nit=f"AUDC{number[-3:]}", legal_name="Cliente de auditoría", created_by=user
    )
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit=f"AUDT{number[-3:]}",
        legal_name="Transportista de auditoría",
        primary_phone="5555",
        email="audit-carrier@example.test",
        created_by=user,
    )
    return Order.objects.create(
        number=number,
        status=CatalogEntry.objects.get(
            catalog_type=CatalogType.ORDER_STATUS, code="solicitud-recibida"
        ),
        customer=customer,
        proposed_carrier=carrier,
        broker=user,
        created_by=user,
        cargo_type=CatalogEntry.objects.filter(
            catalog_type=CatalogType.CARGO_TYPE
        ).first(),
        equipment_type=CatalogEntry.objects.filter(
            catalog_type=CatalogType.EQUIPMENT_TYPE
        ).first(),
        origin="Origen",
        destination="Destino",
        pickup_date=date.today(),
        delivery_date=date.today(),
        customer_rate=Decimal("100"),
        carrier_cost=Decimal("80"),
    )


@pytest.mark.django_db
def test_successful_login_and_logout_are_audited(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")

    client.post(
        reverse("accounts:login"),
        {"username": "broker", "password": "test-pass-123"},
    )
    client.post(reverse("accounts:logout"))

    assert set(AuditEvent.objects.values_list("action", flat=True)) == {"logout", "login"}
    assert AuditEvent.objects.filter(actor=user, action="login").exists()


@pytest.mark.django_db
def test_failed_login_is_audited_without_credentials(client):
    client.post(
        reverse("accounts:login"),
        {"username": "unknown", "password": "not-stored"},
    )

    event = AuditEvent.objects.get(action="login_failed")

    assert event.actor is None
    assert event.metadata == {}


@pytest.mark.django_db
def test_audit_list_requires_permission(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    client.force_login(user)

    response = client.get(reverse("audit:list"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_order_history_requires_audit_permission_before_order_lookup(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="order-history-no-audit")
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    assert client.get(reverse("audit:order_history", args=[999999])).status_code == 403


@pytest.mark.django_db
def test_audit_list_shows_events_to_authorized_user(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="audit-manager", password="test-pass-123")
    permission = Permission.objects.get(
        content_type__app_label="audit", codename="view_auditevent"
    )
    user.user_permissions.add(permission)
    AuditEvent.objects.create(
        actor=user,
        action="test_action",
        entity_type="test_entity",
        entity_id="TEST-001",
    )
    client.force_login(user)

    response = client.get(reverse("audit:list"), {"action": "test_action"})

    assert response.status_code == 200
    assert "TEST-001" in response.content.decode()


@pytest.mark.django_db
def test_audit_events_are_immutable_in_model_and_queryset(db):
    from django.contrib import admin
    from django.db.models.deletion import ProtectedError
    from django.test import RequestFactory

    from .admin import AuditEventAdmin

    user = get_user_model().objects.create_user(username="immutable-audit")
    event = AuditEvent.objects.create(
        actor=user,
        action="test_action",
        entity_type="test_entity",
        entity_id="TEST-IMMUTABLE",
    )

    event.action = "changed_action"
    with pytest.raises(ValidationError):
        event.save()
    with pytest.raises(ValidationError):
        AuditEvent.objects.filter(pk=event.pk).update(action="changed_action")
    with pytest.raises(ValidationError):
        event.delete()
    with pytest.raises(ValidationError):
        AuditEvent.objects.filter(pk=event.pk).delete()
    with pytest.raises(ValidationError):
        AuditEvent.objects.update_or_create(
            pk=event.pk, defaults={"action": "changed_action"}
        )
    with pytest.raises(ProtectedError):
        user.delete()
    audit_admin = AuditEventAdmin(AuditEvent, admin.site)
    request = RequestFactory().get("/admin/audit/auditevent/")
    request.user = user
    assert not audit_admin.has_add_permission(request)
    assert not audit_admin.has_change_permission(request, event)
    assert not audit_admin.has_delete_permission(request, event)

    assert AuditEvent.objects.get(pk=event.pk).action == "test_action"


@pytest.mark.django_db
def test_audit_rejects_sensitive_metadata(db):
    user = get_user_model().objects.create_user(username="metadata-audit")

    with pytest.raises(ValidationError, match="valores sensibles"):
        AuditEvent.objects.create(
            actor=user,
            action="financial_action",
            entity_type="financial_transaction",
            metadata={"amount_usd": "125.00"},
        )


@pytest.mark.django_db
def test_order_history_requires_audit_and_order_view_permissions(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="order-history-auditor")
    order = create_order(user)
    event = AuditEvent.objects.create(
        actor=user,
        order=order,
        action="record_order_event",
        entity_type="order",
        entity_id=str(order.pk),
    )

    client.force_login(user)
    history_url = reverse("audit:order_history", args=[order.pk])
    assert client.get(history_url).status_code == 403

    audit_permission = Permission.objects.get(
        content_type__app_label="audit", codename="view_auditevent"
    )
    order_permission = Permission.objects.get(
        content_type__app_label="orders", codename="view_order"
    )
    user.user_permissions.add(audit_permission)
    assert client.get(history_url).status_code == 403

    user.user_permissions.add(order_permission)
    response = client.get(history_url, {"action": "record_order_event"})

    assert response.status_code == 200
    assert list(response.context["page"].object_list) == [event]
    assert order.number in response.content.decode()


@pytest.mark.django_db
def test_audit_backfill_links_existing_events_and_redacts_sensitive_metadata():
    from django.db.migrations.executor import MigrationExecutor

    from .models import sensitive_metadata_keys

    user = get_user_model().objects.create_user(username="audit-backfill")
    order = create_order(user, number="ORD-AUDIT-002")
    event = AuditEvent.objects.create(
        actor=user,
        action="create_order",
        entity_type="order",
        entity_id=str(order.pk),
    )
    migration = import_module("apps.audit.migrations.0002_complete_order_audit")
    schema_editor = type("SchemaEditor", (), {"connection": connection})()
    migration_apps = MigrationExecutor(connection).loader.project_state().apps
    migration.backfill_order_links_and_redact_metadata(migration_apps, schema_editor)

    event.refresh_from_db()
    assert event.order == order
    assert migration.redact_metadata(
        {"amount_usd": "125.00", "safe_status": "confirmed"}
    ) == {"safe_status": "confirmed"}
    assert not sensitive_metadata_keys(event.metadata)


@pytest.mark.django_db
def test_general_audit_filters_events_by_actor_and_date(client):
    user_model = get_user_model()
    auditor = user_model.objects.create_user(username="event-filter-auditor")
    actor = user_model.objects.create_user(username="event-filter-actor")
    auditor.user_permissions.add(
        Permission.objects.get(
            content_type__app_label="audit", codename="view_auditevent"
        )
    )
    visible_event = AuditEvent.objects.create(
        actor=actor,
        action="filtered_action",
        entity_type="filtered_entity",
        entity_id="FILTER-001",
    )
    AuditEvent.objects.create(
        actor=auditor,
        action="other_action",
        entity_type="other_entity",
        entity_id="FILTER-002",
    )
    client.force_login(auditor)

    response = client.get(
        reverse("audit:list"),
        {
            "action": "filtered_action",
            "entity_type": "filtered_entity",
            "actor": actor.pk,
            "date_from": date.today().isoformat(),
            "date_to": date.today().isoformat(),
        },
    )

    assert response.status_code == 200
    assert list(response.context["page"].object_list) == [visible_event]
    assert "FILTER-001" in response.content.decode()
    assert "FILTER-002" not in response.content.decode()

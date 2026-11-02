from datetime import date, timedelta
from decimal import Decimal
from time import perf_counter

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier, CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer
from apps.documents.models import Document
from apps.finance.models import (
    Commission,
    CommissionRule,
    FinancialReview,
    FinancialStatus,
    FinancialTransaction,
    ReviewStatus,
)
from apps.incidents.models import Incident, IncidentStatus

from .models import Order, OrderClosureStatus
from .services import order_is_overdue


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename__in=codenames)
    )


def prepare_closable_order(order, user):
    for code in (
        "constancia-entrega",
        "factura",
        "comprobante-cobro",
        "comprobante-gasto",
    ):
        Document.objects.create(
            document_type=CatalogEntry.objects.get(
                code=code, catalog_type=CatalogType.DOCUMENT_TYPE
            ),
            order=order,
            created_by=user,
        )
    currency = CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY)
    FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="cobro-cliente"),
        currency=currency,
        amount=Decimal("1500"),
        base_amount_usd=Decimal("1500"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="pago-transportista"),
        cost_type=CatalogEntry.objects.get(
            code="costo-transportista", catalog_type=CatalogType.COST_TYPE
        ),
        currency=currency,
        amount=Decimal("1000"),
        base_amount_usd=Decimal("1000"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    review = FinancialReview.objects.create(
        order=order, status=ReviewStatus.VALIDATED, reviewed_by=user, reviewed_at=timezone.now()
    )
    rule = CommissionRule.objects.create(
        broker=order.broker,
        percentage=Decimal("10"),
        valid_from=order.delivery_date - timedelta(days=1),
        created_by=user,
    )
    Commission.objects.create(
        order=order,
        broker=order.broker,
        rule=rule,
        gross_profit_usd=Decimal("500"),
        commission_rate=Decimal("10"),
        gross_commission_usd=Decimal("50"),
        commission_amount_usd=Decimal("50"),
        calculated_by=user,
    )
    return review


@pytest.fixture
def user(db):
    user = get_user_model().objects.create_user(
        username="broker", password="test-pass-123"
    )
    user.groups.add(Group.objects.get(name="Broker"))
    return user


@pytest.fixture
def order_data(user):
    customer = Customer.objects.create(
        nit="CUST001",
        legal_name="Cliente Demo",
        created_by=user,
    )
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="CARR001",
        legal_name="Transportes Demo",
        primary_phone="5555",
        email="carrier@example.com",
        created_by=user,
        is_validated=True,
    )
    return {
        "broker": user.pk,
        "customer": customer.pk,
        "proposed_carrier": carrier.pk,
        "cargo_type": CatalogEntry.objects.filter(
            catalog_type=CatalogType.CARGO_TYPE, is_active=True
        ).first().pk,
        "equipment_type": CatalogEntry.objects.filter(
            catalog_type=CatalogType.EQUIPMENT_TYPE, is_active=True
        ).first().pk,
        "origin": "Ciudad A",
        "destination": "Ciudad B",
        "pickup_date": date.today(),
        "delivery_date": date.today() + timedelta(days=2),
        "customer_rate": Decimal("1500.00"),
        "carrier_cost": Decimal("1000.00"),
    }


@pytest.mark.django_db
def test_order_created_with_sequential_number_and_initial_status(client, user, order_data):
    grant(user, "add_order", "view_order")
    other_broker = get_user_model().objects.create_user(username="spoofed-order-broker")
    other_broker.groups.add(Group.objects.get(name="Broker"))
    client.force_login(user)
    response = client.post(
        reverse("orders:create"), {**order_data, "broker": other_broker.pk}
    )
    order = Order.objects.get()

    assert response.status_code == 302
    assert order.number.startswith(f"ORD-{date.today().year}-")
    assert order.number.endswith("000001")
    assert order.status.code == "solicitud-recibida"
    assert order.closure_status == OrderClosureStatus.OPEN
    assert order.broker == user
    assert order.created_by == user
    list_response = client.get(reverse("orders:list"))
    assert "justify-content-between" in list_response.content.decode()
    assert "btn btn-primary ms-auto" in list_response.content.decode()


@pytest.mark.django_db
def test_broker_order_scope_includes_creator_or_current_assignment(client, user, order_data):
    grant(user, "add_order", "view_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    created_order = Order.objects.get()
    other_broker = get_user_model().objects.create_user(username="other-order-broker")
    other_broker.groups.add(Group.objects.get(name="Broker"))
    grant(other_broker, "view_order")

    created_order.broker = other_broker
    created_order.save(update_fields=("broker", "updated_at"))
    assigned_order = Order.objects.create(
        status=created_order.status,
        customer=created_order.customer,
        proposed_carrier=created_order.proposed_carrier,
        broker=user,
        created_by=other_broker,
        cargo_type=created_order.cargo_type,
        equipment_type=created_order.equipment_type,
        origin=created_order.origin,
        destination=created_order.destination,
        pickup_date=created_order.pickup_date,
        delivery_date=created_order.delivery_date,
        customer_rate=created_order.customer_rate,
        carrier_cost=created_order.carrier_cost,
        number="ORD-SCOPE-ASSIGNED",
    )
    private_order = Order.objects.create(
        status=created_order.status,
        customer=created_order.customer,
        proposed_carrier=created_order.proposed_carrier,
        broker=other_broker,
        created_by=other_broker,
        cargo_type=created_order.cargo_type,
        equipment_type=created_order.equipment_type,
        origin=created_order.origin,
        destination=created_order.destination,
        pickup_date=created_order.pickup_date,
        delivery_date=created_order.delivery_date,
        customer_rate=created_order.customer_rate,
        carrier_cost=created_order.carrier_cost,
        number="ORD-SCOPE-PRIVATE",
    )

    response = client.get(reverse("orders:list"))

    assert {order.pk for order in response.context["orders"]} == {
        created_order.pk,
        assigned_order.pk,
    }
    assert client.get(
        reverse("orders:detail", args=[private_order.pk])
    ).status_code == 404


@pytest.mark.django_db
def test_order_list_paginates_10000_orders_in_database(user, order_data, record_property):
    grant(user, "view_order")
    status_id = CatalogEntry.objects.get(code="solicitud-recibida").pk
    shared_fields = {
        "status_id": status_id,
        "customer_id": order_data["customer"],
        "proposed_carrier_id": order_data["proposed_carrier"],
        "broker_id": user.pk,
        "created_by_id": user.pk,
        "cargo_type_id": order_data["cargo_type"],
        "equipment_type_id": order_data["equipment_type"],
        "origin": order_data["origin"],
        "destination": order_data["destination"],
        "pickup_date": order_data["pickup_date"],
        "delivery_date": order_data["delivery_date"],
        "customer_rate": order_data["customer_rate"],
        "carrier_cost": order_data["carrier_cost"],
        "updated_at": timezone.now(),
    }
    Order.objects.bulk_create(
        [
            Order(number=f"ORD-PERF-{index:05d}", **shared_fields)
            for index in range(10_000)
        ],
        batch_size=500,
    )

    client = Client()
    client.force_login(user)
    started = perf_counter()
    with CaptureQueriesContext(connection) as captured_queries:
        response = client.get(reverse("orders:list"))
    single_request_seconds = perf_counter() - started

    assert response.status_code == 200
    assert len(response.context["orders"]) == 25
    assert any(
        "LIMIT 25" in query["sql"].upper() for query in captured_queries.captured_queries
    )
    assert single_request_seconds < 2
    record_property("order_list_10000_seconds", f"{single_request_seconds:.3f}")


@pytest.mark.django_db
def test_administrator_creating_order_must_assign_it_to_a_broker(client, user, order_data):
    administrator = get_user_model().objects.create_user(username="order-creator-admin")
    administrator.groups.add(Group.objects.get(name="Administrador"))
    new_broker = get_user_model().objects.create_user(username="order-reassigned-broker")
    new_broker.groups.add(Group.objects.get(name="Broker"))
    client.force_login(administrator)

    response = client.post(reverse("orders:create"), order_data)

    order = Order.objects.get()
    assert response.status_code == 302
    assert order.broker == user
    assert order.created_by == administrator

    order.customer.brokers.add(new_broker)
    order.proposed_carrier.brokers.add(new_broker)
    update_response = client.post(
        reverse("orders:update", args=[order.pk]),
        {**order_data, "broker": new_broker.pk},
    )
    order.refresh_from_db()
    assert update_response.status_code == 302
    assert order.broker == new_broker
    assert order.created_by == administrator


@pytest.mark.django_db
def test_order_assignment_requires_broker_access_to_selected_master_records(
    client, user, order_data
):
    administrator = get_user_model().objects.create_user(username="order-assignment-admin")
    administrator.groups.add(Group.objects.get(name="Administrador"))
    broker = get_user_model().objects.create_user(username="unassigned-order-broker")
    broker.groups.add(Group.objects.get(name="Broker"))
    client.force_login(administrator)

    response = client.post(
        reverse("orders:create"), {**order_data, "broker": broker.pk}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["broker"]
    assert not Order.objects.exists()


@pytest.mark.django_db
def test_order_rejects_delivery_before_pickup(order_data, user):
    from .forms import OrderForm

    order_data["delivery_date"] = date.today() - timedelta(days=1)
    form = OrderForm(data=order_data)
    assert not form.is_valid()
    assert "delivery_date" in form.errors


@pytest.mark.django_db
def test_broker_cannot_confirm_carrier(client, user, order_data):
    grant(user, "add_order", "view_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()

    response = client.post(reverse("orders:confirm_carrier", args=[order.pk]))

    assert response.status_code == 403
    order.refresh_from_db()
    assert order.confirmed_carrier is None


@pytest.mark.django_db
def test_dispatcher_can_confirm_validated_carrier(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    user.groups.add(Group.objects.get(name="Dispatcher"))
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()

    response = client.post(reverse("orders:confirm_carrier", args=[order.pk]))

    assert response.status_code == 302
    order.refresh_from_db()
    assert order.confirmed_carrier == order.proposed_carrier
    assert order.formalized_by == user


@pytest.mark.django_db
def test_order_status_transition_records_history(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    target = CatalogEntry.objects.get(code="en-negociacion")

    response = client.post(
        reverse("orders:change_status", args=[order.pk]),
        {"status": target.pk, "observation": "Se inició negociación."},
    )

    order.refresh_from_db()
    assert response.status_code == 302
    assert order.status == target
    assert order.status_history.filter(observation="Se inició negociación.").exists()


@pytest.mark.django_db
def test_invalid_order_status_transition_is_rejected(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    target = CatalogEntry.objects.get(code="entregada")

    response = client.post(
        reverse("orders:change_status", args=[order.pk]),
        {"status": target.pk},
    )

    order.refresh_from_db()
    assert response.status_code == 302
    assert order.status.code == "solicitud-recibida"


@pytest.mark.django_db
def test_order_cannot_be_assigned_until_dispatcher_confirms_proposed_carrier(
    client, user, order_data
):
    grant(user, "add_order", "view_order", "change_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()

    for code in ("en-negociacion", "pendiente-documentacion", "validada"):
        response = client.post(
            reverse("orders:change_status", args=[order.pk]),
            {"status": CatalogEntry.objects.get(code=code).pk},
        )
        assert response.status_code == 302

    assigned = CatalogEntry.objects.get(code="asignada")
    response = client.post(
        reverse("orders:change_status", args=[order.pk]), {"status": assigned.pk}
    )

    order.refresh_from_db()
    assert response.status_code == 302
    assert order.status.code == "validada"
    assert order.confirmed_carrier is None
    assert order.status_history.count() == 4


@pytest.mark.parametrize(
    "carrier_condition", ("is_active", "is_validated", "proposal_changed")
)
@pytest.mark.django_db
def test_order_cannot_be_assigned_if_confirmed_carrier_is_no_longer_eligible(
    client, user, order_data, carrier_condition
):
    grant(user, "add_order", "view_order", "change_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()

    for code in ("en-negociacion", "pendiente-documentacion", "validada"):
        client.post(
            reverse("orders:change_status", args=[order.pk]),
            {"status": CatalogEntry.objects.get(code=code).pk},
        )

    dispatcher = get_user_model().objects.create_user(
        username=f"confirm-{carrier_condition}"
    )
    dispatcher.groups.add(Group.objects.get(name="Dispatcher"))
    grant(dispatcher, "view_order", "change_order")
    dispatcher_client = Client()
    dispatcher_client.force_login(dispatcher)
    confirmation = dispatcher_client.post(
        reverse("orders:confirm_carrier", args=[order.pk])
    )
    assert confirmation.status_code == 302

    if carrier_condition == "proposal_changed":
        Order.objects.filter(pk=order.pk).update(proposed_carrier=None)
    else:
        carrier = order.proposed_carrier
        setattr(carrier, carrier_condition, False)
        carrier.save(update_fields=(carrier_condition, "updated_at"))
    assigned = CatalogEntry.objects.get(code="asignada")
    response = client.post(
        reverse("orders:change_status", args=[order.pk]), {"status": assigned.pk}
    )

    order.refresh_from_db()
    assert response.status_code == 302
    assert order.status.code == "validada"


@pytest.mark.django_db
def test_order_overdue_uses_calendar_days(client, user, order_data):
    grant(user, "add_order", "view_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()

    for days, overdue in ((6, False), (7, True), (8, True)):
        changed_at = timezone.now() - timedelta(days=days)
        Order.objects.filter(pk=order.pk).update(updated_at=changed_at)
        order.refresh_from_db()
        assert order_is_overdue(order) is overdue


@pytest.mark.django_db
def test_order_list_filters_overdue_orders_without_including_delivered(client, user, order_data):
    grant(user, "add_order", "view_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    Order.objects.filter(pk=order.pk).update(updated_at=timezone.now() - timedelta(days=7))

    overdue_response = client.get(reverse("orders:list"), {"atrasadas": "1"})

    assert overdue_response.status_code == 200
    assert list(overdue_response.context["orders"]) == [order]
    assert overdue_response.context["orders"][0].is_overdue

    order.status = CatalogEntry.objects.get(code="entregada")
    order.save(update_fields=("status", "updated_at"))
    delivered_response = client.get(reverse("orders:list"), {"atrasadas": "1"})

    assert list(delivered_response.context["orders"]) == []


@pytest.mark.django_db
def test_cancel_requires_observation(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    target = CatalogEntry.objects.get(code="cancelada")

    client.post(reverse("orders:change_status", args=[order.pk]), {"status": target.pk})

    order.refresh_from_db()
    assert order.status.code == "solicitud-recibida"


@pytest.mark.django_db
def test_broker_cannot_close_order(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    delivered = CatalogEntry.objects.get(code="entregada")
    closing = CatalogEntry.objects.get(code="pendiente-cierre")
    Order.objects.filter(pk=order.pk).update(status=delivered)
    order.refresh_from_db()

    client.post(reverse("orders:change_status", args=[order.pk]), {"status": closing.pk})

    order.refresh_from_db()
    assert order.status == delivered


@pytest.mark.django_db
def test_dispatcher_closes_and_reopens_order(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    dispatcher = Group.objects.get(name="Dispatcher")
    user.groups.add(dispatcher)
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    delivered = CatalogEntry.objects.get(code="entregada")
    closing = CatalogEntry.objects.get(code="pendiente-cierre")
    closed = CatalogEntry.objects.get(code="cerrada")
    reopened = CatalogEntry.objects.get(code="reabierta")
    Order.objects.filter(pk=order.pk).update(status=delivered)
    prepare_closable_order(order, user)

    client.post(reverse("orders:change_status", args=[order.pk]), {"status": closing.pk})
    client.post(reverse("orders:change_status", args=[order.pk]), {"status": closed.pk})
    saved_order = Order.objects.get(pk=order.pk)
    assert saved_order.status == delivered
    assert saved_order.closure_status == OrderClosureStatus.CLOSED
    closed_orders = client.get(reverse("orders:list"), {"closure": "closed"})
    assert list(closed_orders.context["orders"].object_list) == [saved_order]
    assert AuditEvent.objects.filter(
        action="change_order_status", order=saved_order
    ).count() == 2

    client.post(
        reverse("orders:change_status", args=[order.pk]),
        {"status": reopened.pk, "observation": "Se requiere revisión administrativa."},
    )

    order.refresh_from_db()
    assert order.status == delivered
    assert order.closure_status == OrderClosureStatus.REOPENED


@pytest.mark.django_db
def test_integral_order_flow_from_creation_through_reopening(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    client.force_login(user)

    creation = client.post(reverse("orders:create"), order_data)
    assert creation.status_code == 302
    order = Order.objects.get()
    assert order.status.code == "solicitud-recibida"

    for code in ("en-negociacion", "pendiente-documentacion", "validada"):
        response = client.post(
            reverse("orders:change_status", args=[order.pk]),
            {"status": CatalogEntry.objects.get(code=code).pk},
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status.code == code

    dispatcher = get_user_model().objects.create_user(username="integral-dispatcher")
    dispatcher.groups.add(Group.objects.get(name="Dispatcher"))
    grant(dispatcher, "view_order", "change_order")
    dispatcher_client = Client()
    dispatcher_client.force_login(dispatcher)
    confirmation = dispatcher_client.post(
        reverse("orders:confirm_carrier", args=[order.pk])
    )
    assert confirmation.status_code == 302
    order.refresh_from_db()
    assert order.confirmed_carrier == order.proposed_carrier
    assert order.formalized_by == dispatcher

    for code in ("asignada", "en-recogida", "en-transito", "entregada"):
        response = client.post(
            reverse("orders:change_status", args=[order.pk]),
            {"status": CatalogEntry.objects.get(code=code).pk},
        )
        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status.code == code

    prepare_closable_order(order, dispatcher)
    for code, observation in (
        ("pendiente-cierre", "Se completó la validación del expediente."),
        ("cerrada", "Cierre administrativo confirmado."),
        ("reabierta", "Se requiere una revisión posterior al cierre."),
    ):
        response = dispatcher_client.post(
            reverse("orders:change_status", args=[order.pk]),
            {
                "status": CatalogEntry.objects.get(code=code).pk,
                "observation": observation,
            },
        )
        assert response.status_code == 302
        order.refresh_from_db()
        if code == "reabierta":
            assert order.closure_status == OrderClosureStatus.REOPENED
        else:
            assert order.status.code == "entregada"
            assert order.closure_status == {
                "pendiente-cierre": OrderClosureStatus.PENDING,
                "cerrada": OrderClosureStatus.CLOSED,
            }[code]

    assert order.status_history.count() == 11
    assert AuditEvent.objects.filter(order=order, action="change_order_status").count() == 10


@pytest.mark.django_db
def test_closed_order_cannot_be_edited_through_application_or_admin(
    client, user, order_data
):
    grant(user, "add_order", "view_order", "change_order")
    user.groups.add(Group.objects.get(name="Dispatcher"))
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    Order.objects.filter(pk=order.pk).update(closure_status=OrderClosureStatus.CLOSED)
    order.refresh_from_db()

    detail = client.get(reverse("orders:detail", args=[order.pk]))
    edit = client.get(reverse("orders:update", args=[order.pk]))
    update = client.post(reverse("orders:update", args=[order.pk]), order_data)

    assert detail.status_code == 200
    assert "Editar" not in detail.content.decode()
    assert edit.status_code == 403
    assert update.status_code == 403
    assert not AuditEvent.objects.filter(
        action="update_order", entity_id=str(order.pk)
    ).exists()
    assert Order.objects.get(pk=order.pk).closure_status == OrderClosureStatus.CLOSED

    from django.contrib import admin
    from django.test import RequestFactory

    from .admin import OrderAdmin

    model_admin = OrderAdmin(Order, admin.site)
    request = RequestFactory().get("/admin/")
    request.user = user
    assert not model_admin.has_change_permission(request, order)
    assert {"status", "closure_status"}.issubset(
        model_admin.get_readonly_fields(request, order)
    )


@pytest.mark.django_db
def test_closure_status_migration_preserves_operational_history_and_fallback(
    user, order_data
):
    from importlib import import_module

    from django.apps import apps as django_apps
    from django.db import connection

    from .models import OrderStatusHistory

    delivered = CatalogEntry.objects.get(code="entregada")
    closed = CatalogEntry.objects.get(code="cerrada")

    def create_legacy_closed_order(number):
        return Order.objects.create(
            number=number,
            status=closed,
            customer_id=order_data["customer"],
            proposed_carrier_id=order_data["proposed_carrier"],
            broker=user,
            created_by=user,
            cargo_type_id=order_data["cargo_type"],
            equipment_type_id=order_data["equipment_type"],
            origin=order_data["origin"],
            destination=order_data["destination"],
            pickup_date=order_data["pickup_date"],
            delivery_date=order_data["delivery_date"],
            customer_rate=order_data["customer_rate"],
            carrier_cost=order_data["carrier_cost"],
        )

    with_history = create_legacy_closed_order("ORD-CLOSE-MIG-01")
    initial = CatalogEntry.objects.get(code="solicitud-recibida")
    OrderStatusHistory.objects.create(
        order=with_history, status=initial, changed_by=user
    )
    OrderStatusHistory.objects.create(
        order=with_history,
        previous_status=initial,
        status=delivered,
        changed_by=user,
    )
    OrderStatusHistory.objects.create(
        order=with_history,
        previous_status=delivered,
        status=closed,
        changed_by=user,
    )
    without_history = create_legacy_closed_order("ORD-CLOSE-MIG-02")

    migration = import_module("apps.orders.migrations.0005_separate_closure_status")
    schema_editor = type("SchemaEditor", (), {"connection": connection})()
    migration.separate_closure_status(django_apps, schema_editor)

    with_history.refresh_from_db()
    without_history.refresh_from_db()
    assert with_history.status == delivered
    assert with_history.closure_status == OrderClosureStatus.CLOSED
    assert without_history.status == delivered
    assert without_history.closure_status == OrderClosureStatus.CLOSED


@pytest.mark.django_db
def test_close_requires_delivery_evidence(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    user.groups.add(Group.objects.get(name="Dispatcher"))
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    delivered = CatalogEntry.objects.get(code="entregada")
    closing = CatalogEntry.objects.get(code="pendiente-cierre")
    closed = CatalogEntry.objects.get(code="cerrada")
    Order.objects.filter(pk=order.pk).update(status=delivered)
    order.refresh_from_db()
    prepare_closable_order(order, user)
    Document.objects.filter(order=order, document_type__code="constancia-entrega").delete()

    client.post(reverse("orders:change_status", args=[order.pk]), {"status": closing.pk})
    client.post(reverse("orders:change_status", args=[order.pk]), {"status": closed.pk})

    order.refresh_from_db()
    assert order.status == delivered
    assert order.closure_status == OrderClosureStatus.PENDING


@pytest.mark.django_db
def test_critical_open_incident_blocks_close(client, user, order_data):
    grant(user, "add_order", "view_order", "change_order")
    user.groups.add(Group.objects.get(name="Dispatcher"))
    client.force_login(user)
    client.post(reverse("orders:create"), order_data)
    order = Order.objects.get()
    delivered = CatalogEntry.objects.get(code="entregada")
    closing = CatalogEntry.objects.get(code="pendiente-cierre")
    closed = CatalogEntry.objects.get(code="cerrada")
    Order.objects.filter(pk=order.pk).update(status=delivered)
    order.refresh_from_db()
    prepare_closable_order(order, user)
    Incident.objects.create(
        order=order,
        incident_type=CatalogEntry.objects.get(code="dano-en-mercancia"),
        priority=CatalogEntry.objects.get(code="critica"),
        status=IncidentStatus.OPEN,
        title="Daño crítico",
        description="Incidencia abierta.",
        created_by=user,
    )

    client.post(reverse("orders:change_status", args=[order.pk]), {"status": closing.pk})
    client.post(reverse("orders:change_status", args=[order.pk]), {"status": closed.pk})

    order.refresh_from_db()
    assert order.status == delivered
    assert order.closure_status == OrderClosureStatus.PENDING

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier, CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType, SystemConfiguration
from apps.customers.models import Customer
from apps.finance.models import (
    BrokerDebt,
    CommercialAdjustmentStatus,
    CommercialAdjustmentTarget,
    Commission,
    CommissionDebtApplication,
    CommissionRule,
    CommissionStatus,
    FinancialStatus,
    FinancialTransaction,
)
from apps.finance.services import register_commercial_adjustment, review_commercial_adjustment
from apps.incidents.models import Incident
from apps.orders.models import Order, OrderClosureStatus

from .services import report_page_size


@pytest.fixture
def report_order(db):
    user_model = get_user_model()
    broker = user_model.objects.create_user(
        username="report-broker", password="test-pass-123"
    )
    broker.groups.add(Group.objects.get(name="Broker"))
    customer = Customer.objects.create(
        nit="REP001", legal_name="Cliente Reportes", created_by=broker
    )
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="REP002",
        legal_name="Transportes Reportes",
        primary_phone="5555",
        email="reports@example.com",
        created_by=broker,
    )
    return Order.objects.create(
        status=CatalogEntry.objects.get(code="solicitud-recibida"),
        customer=customer,
        proposed_carrier=carrier,
        broker=broker,
        created_by=broker,
        cargo_type=CatalogEntry.objects.filter(catalog_type=CatalogType.CARGO_TYPE).first(),
        equipment_type=CatalogEntry.objects.filter(
            catalog_type=CatalogType.EQUIPMENT_TYPE
        ).first(),
        origin="Origen",
        destination="Destino",
        pickup_date=date.today(),
        delivery_date=date.today() + timedelta(days=2),
        customer_rate=Decimal("1000"),
        carrier_cost=Decimal("700"),
        number="ORD-REPORT-001",
    )


@pytest.mark.django_db
def test_reports_require_order_permission(client):
    user = get_user_model().objects.create_user(username="no-report", password="test-pass-123")
    client.force_login(user)

    assert client.get(reverse("reports:dashboard")).status_code == 403


@pytest.mark.django_db
def test_operational_report_is_available_and_filters_by_customer(client, report_order):
    user = report_order.broker
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    response = client.get(
        reverse("reports:detail", args=["orders-customer"]),
        {"customer": report_order.customer_id},
    )

    assert response.status_code == 200
    assert list(response.context["rows"])[0] == report_order
    assert response.context["report_type"] == "orders"
    assert response.context["report_group_by"] == "customer"
    assert "Estado financiero" in response.content.decode()


@pytest.mark.django_db
def test_order_report_filters_closure_status_separately(client, report_order):
    user = report_order.broker
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order")
    )
    report_order.closure_status = OrderClosureStatus.CLOSED
    report_order.save(update_fields=("closure_status", "updated_at"))
    client.force_login(user)

    response = client.get(
        reverse("reports:detail", args=["orders"]),
        {"closure_status": OrderClosureStatus.CLOSED},
    )
    open_response = client.get(
        reverse("reports:detail", args=["orders"]),
        {"closure_status": OrderClosureStatus.OPEN},
    )

    assert response.status_code == 200
    assert list(response.context["rows"]) == [report_order]
    assert "Estado de cierre" in response.content.decode()
    assert list(open_response.context["rows"]) == []


@pytest.mark.django_db
def test_broker_reports_are_scoped_before_filtering_and_rendering(client, report_order):
    other_broker = get_user_model().objects.create_user(username="report-other-broker")
    other_broker.groups.add(Group.objects.get(name="Broker"))
    other_customer = Customer.objects.create(
        nit="REP003", legal_name="Cliente privado", created_by=other_broker
    )
    other_order = Order.objects.create(
        status=report_order.status,
        customer=other_customer,
        proposed_carrier=report_order.proposed_carrier,
        broker=other_broker,
        created_by=other_broker,
        cargo_type=report_order.cargo_type,
        equipment_type=report_order.equipment_type,
        origin=report_order.origin,
        destination=report_order.destination,
        pickup_date=report_order.pickup_date,
        delivery_date=report_order.delivery_date,
        customer_rate=report_order.customer_rate,
        carrier_cost=report_order.carrier_cost,
        number="ORD-REPORT-PRIVATE",
    )
    broker = report_order.broker
    broker.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order"),
        Permission.objects.get(content_type__app_label="customers", codename="view_customer"),
    )
    client.force_login(broker)

    orders_response = client.get(reverse("reports:detail", args=["orders"]))
    filtered_response = client.get(
        reverse("reports:detail", args=["orders"]), {"customer": other_customer.pk}
    )
    customers_response = client.get(reverse("reports:detail", args=["customers"]))

    assert list(orders_response.context["rows"]) == [report_order]
    assert filtered_response.status_code == 400
    assert list(filtered_response.context["rows"]) == []
    assert list(customers_response.context["rows"]) == [report_order.customer]
    assert other_order not in orders_response.context["rows"]


@pytest.mark.django_db
def test_master_assignment_migrations_infer_brokers_from_orders(report_order):
    from importlib import import_module

    from django.apps import apps as django_apps

    creator = get_user_model().objects.create_user(username="master-migration-admin")
    creator.groups.add(Group.objects.get(name="Administrador"))
    customer = Customer.objects.create(
        nit="MIGRATE01", legal_name="Cliente histórico", created_by=creator
    )
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="MIGRATE02",
        legal_name="Transportista histórico",
        primary_phone="5555",
        email="migration@example.test",
        created_by=creator,
    )
    creator_only_customer = Customer.objects.create(
        nit="MIGRATE03", legal_name="Sin órdenes históricas", created_by=report_order.broker
    )
    creator_only_carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="MIGRATE04",
        legal_name="Sin órdenes históricas",
        primary_phone="5556",
        email="migration-fallback@example.test",
        created_by=report_order.broker,
    )
    Order.objects.create(
        status=report_order.status,
        customer=customer,
        proposed_carrier=carrier,
        broker=report_order.broker,
        created_by=creator,
        cargo_type=report_order.cargo_type,
        equipment_type=report_order.equipment_type,
        origin=report_order.origin,
        destination=report_order.destination,
        pickup_date=report_order.pickup_date,
        delivery_date=report_order.delivery_date,
        customer_rate=report_order.customer_rate,
        carrier_cost=report_order.carrier_cost,
        number="ORD-MIGRATION-01",
    )

    customer_migration = import_module(
        "apps.customers.migrations.0002_customer_brokers"
    )
    carrier_migration = import_module("apps.carriers.migrations.0003_carrier_brokers")
    customer_migration.backfill_customer_brokers(django_apps, None)
    carrier_migration.backfill_carrier_brokers(django_apps, None)

    assert list(customer.brokers.all()) == [report_order.broker]
    assert list(carrier.brokers.all()) == [report_order.broker]
    assert list(creator_only_customer.brokers.all()) == [report_order.broker]
    assert list(creator_only_carrier.brokers.all()) == [report_order.broker]


@pytest.mark.django_db
def test_dashboard_has_one_orders_report_and_preserves_quick_access(client, report_order):
    user = report_order.broker
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    response = client.get(reverse("reports:dashboard"))
    content = response.content.decode()

    assert response.status_code == 200
    assert dict(response.context["report_choices"])["orders"] == "Reporte de órdenes"
    assert content.count("Reporte de órdenes") == 1
    assert "Órdenes por estado" in content
    assert "Órdenes por cliente" in content
    assert "Órdenes atrasadas" in content


@pytest.mark.django_db
def test_historical_inactive_entities_remain_available_as_filters(client, report_order):
    report_order.customer.is_active = False
    report_order.customer.save()
    report_order.proposed_carrier.is_active = False
    report_order.proposed_carrier.save()
    report_order.broker.is_active = False
    report_order.broker.save()
    report_order.status.is_active = False
    report_order.status.save()
    report_order.cargo_type.is_active = False
    report_order.cargo_type.save()

    viewer = get_user_model().objects.create_user(
        username="historical-report-viewer", password="test-pass-123"
    )
    viewer.groups.add(Group.objects.get(name="Gerente general"))
    viewer.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(viewer)

    response = client.get(
        reverse("reports:detail", args=["orders"]),
        {
            "customer": report_order.customer_id,
            "carrier": report_order.proposed_carrier_id,
            "broker": report_order.broker_id,
            "status": report_order.status_id,
            "cargo_type": report_order.cargo_type_id,
        },
    )

    assert response.status_code == 200
    assert list(response.context["rows"]) == [report_order]


@pytest.mark.django_db
def test_invalid_order_filters_show_errors_without_running_unfiltered_report(
    client, report_order
):
    user = report_order.broker
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    response = client.get(
        reverse("reports:detail", args=["orders"]),
        {"date_from": date.today() + timedelta(days=1), "date_to": date.today()},
    )

    assert response.status_code == 400
    assert list(response.context["rows"]) == []
    assert response.context["form"].errors["date_to"]
    assert "Corrija los filtros" in response.content.decode()


@pytest.mark.django_db
def test_delivery_date_basis_filters_orders_by_delivery_date(client, report_order):
    user = report_order.broker
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    response = client.get(
        reverse("reports:detail", args=["orders"]),
        {
            "date_basis": "delivery",
            "date_from": report_order.delivery_date,
            "date_to": report_order.delivery_date,
        },
    )

    assert response.status_code == 200
    assert list(response.context["rows"]) == [report_order]


@pytest.mark.django_db
def test_overdue_shortcut_preselects_existing_overdue_definition(client, report_order):
    user = report_order.broker
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    Order.objects.filter(pk=report_order.pk).update(
        updated_at=timezone.now() - timedelta(days=10)
    )
    client.force_login(user)

    response = client.get(reverse("reports:detail", args=["orders-overdue"]))

    assert response.status_code == 200
    assert response.context["report_type"] == "orders"
    assert response.context["form"].cleaned_data["overdue"] == "yes"
    assert list(response.context["rows"])[0].pk == report_order.pk
    assert "sin actualización durante 7 días" in response.content.decode()


@pytest.mark.django_db
def test_group_and_filters_are_preserved_on_pagination_and_export(client, report_order):
    Order.objects.create(
        status=report_order.status,
        customer=report_order.customer,
        proposed_carrier=report_order.proposed_carrier,
        broker=report_order.broker,
        created_by=report_order.created_by,
        cargo_type=report_order.cargo_type,
        equipment_type=report_order.equipment_type,
        origin=report_order.origin,
        destination=report_order.destination,
        pickup_date=report_order.pickup_date,
        delivery_date=report_order.delivery_date,
        customer_rate=report_order.customer_rate,
        carrier_cost=report_order.carrier_cost,
        number="ORD-REPORT-002",
    )
    SystemConfiguration.objects.update_or_create(
        key="report-page-size", defaults={"value": "1", "is_active": True}
    )
    manager = get_user_model().objects.create_user(
        username="report-export-manager", password="test-pass-123"
    )
    manager.groups.add(Group.objects.get(name="Gerente general"))
    manager.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(manager)
    report_url = reverse("reports:detail", args=["orders"])
    filters = {
        "group_by": "customer",
        "customer": report_order.customer_id,
        "date_basis": "created",
        "date_from": date.today() - timedelta(days=1),
        "date_to": date.today() + timedelta(days=1),
    }

    response = client.get(report_url, filters)
    csv_response = client.get(report_url, {**filters, "format": "csv"})

    assert response.status_code == 200
    assert response.context["page_obj"].has_next()
    assert "group_by=customer" in response.content.decode()
    assert f"customer={report_order.customer_id}" in response.content.decode()
    assert "date_basis=created" in response.content.decode()
    assert "date_from=" in response.content.decode()
    assert csv_response.status_code == 200
    assert "ORD-REPORT-001" in csv_response.content.decode()
    assert "ORD-REPORT-002" in csv_response.content.decode()
    assert AuditEvent.objects.filter(
        action="export_report", entity_id="orders", metadata__filters__group_by="customer"
    ).exists()


@pytest.mark.django_db
def test_invalid_csv_filters_return_validation_error_without_export_audit(client, report_order):
    manager = get_user_model().objects.create_user(
        username="invalid-csv-manager", password="test-pass-123"
    )
    manager.groups.add(Group.objects.get(name="Gerente general"))
    manager.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(manager)

    response = client.get(
        reverse("reports:detail", args=["orders"]),
        {
            "date_from": date.today() + timedelta(days=1),
            "date_to": date.today(),
            "format": "csv",
        },
    )

    assert response.status_code == 400
    assert not AuditEvent.objects.filter(action="export_report", entity_id="orders").exists()


@pytest.mark.django_db
def test_financial_summary_period_nets_adjustments_on_their_transaction_date(
    client, report_order
):
    currency = CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY)
    movement_type = CatalogEntry.objects.get(code="cobro-cliente")
    original_collection = FinancialTransaction.objects.create(
        order=report_order,
        movement_type=movement_type,
        currency=currency,
        amount=Decimal("100.00"),
        transaction_date=date.today() - timedelta(days=30),
        status=FinancialStatus.CONFIRMED,
        created_by=report_order.broker,
    )
    FinancialTransaction.objects.create(
        order=report_order,
        movement_type=CatalogEntry.objects.get(code="pago-transportista"),
        cost_type=CatalogEntry.objects.get(
            code="costo-transportista", catalog_type=CatalogType.COST_TYPE
        ),
        currency=currency,
        amount=Decimal("40.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=report_order.broker,
    )
    FinancialTransaction.objects.create(
        order=report_order,
        movement_type=movement_type,
        currency=currency,
        amount=Decimal("20.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=report_order.broker,
        adjustment_of=original_collection,
        description="Compensación en el período consultado.",
    )
    dispatcher = get_user_model().objects.create_user(
        username="period-adjustment-dispatcher", password="test-pass-123"
    )
    dispatcher.groups.add(Group.objects.get(name="Dispatcher"))
    administrative = get_user_model().objects.create_user(
        username="period-adjustment-admin", password="test-pass-123"
    )
    administrative.groups.add(Group.objects.get(name="Gerente administrativo"))
    customer_adjustment = register_commercial_adjustment(
        order=report_order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CUSTOMER,
        amount_usd=Decimal("10.00"),
        reason="Aumento aprobado para el acuerdo.",
    )
    carrier_adjustment = register_commercial_adjustment(
        order=report_order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CARRIER,
        amount_usd=Decimal("-5.00"),
        reason="Reducción aprobada para el acuerdo.",
    )
    for adjustment in (customer_adjustment, carrier_adjustment):
        review_commercial_adjustment(
            adjustment=adjustment,
            actor=administrative,
            decision=CommercialAdjustmentStatus.APPROVED,
        )
    manager = get_user_model().objects.create_user(
        username="financial-summary-manager", password="test-pass-123"
    )
    manager.groups.add(Group.objects.get(name="Gerente general"))
    manager.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order"),
        *Permission.objects.filter(
            content_type__app_label="finance", codename="view_financialtransaction"
        ),
    )
    client.force_login(manager)

    report_url = reverse("reports:detail", args=["financial-summary"])
    filters = {"date_from": date.today(), "date_to": date.today()}
    response = client.get(report_url, filters)
    csv_response = client.get(report_url, {**filters, "format": "csv"})
    dashboard = client.get(reverse("reports:dashboard"))

    row = list(response.context["rows"])[0]
    assert response.status_code == 200
    assert row.income_usd == Decimal("-20.00")
    assert row.expenses_usd == Decimal("40.00")
    assert row.profit_usd == Decimal("-60.00")
    assert row.customer_received_usd == Decimal("80.00")
    assert row.customer_amount_due_usd == Decimal("1010.00")
    assert row.customer_balance_usd == Decimal("930.00")
    assert row.carrier_paid_usd == Decimal("40.00")
    assert row.carrier_amount_due_usd == Decimal("695.00")
    assert row.carrier_balance_usd == Decimal("655.00")
    assert dashboard.context["metrics"]["profit_usd"] == Decimal("40.00")
    assert "id_date_from" not in dashboard.content.decode()
    assert csv_response.status_code == 200
    assert "-20.00" in csv_response.content.decode()
    assert "1010.00" in csv_response.content.decode()
    assert "930.00" in csv_response.content.decode()
    assert "655.00" in csv_response.content.decode()


@pytest.mark.django_db
def test_commissions_report_summarizes_by_broker_and_drills_to_order_details(
    client, report_order
):
    user = report_order.broker
    rule = CommissionRule.objects.create(
        broker=user,
        percentage=Decimal("10"),
        valid_from=date.today() - timedelta(days=1),
        created_by=user,
    )
    first_commission = Commission.objects.create(
        order=report_order,
        broker=user,
        rule=rule,
        gross_profit_usd=Decimal("100"),
        commission_rate=Decimal("10"),
        gross_commission_usd=Decimal("10"),
        commission_amount_usd=Decimal("10"),
        calculated_by=user,
    )
    second_order = Order.objects.create(
        status=report_order.status,
        customer=report_order.customer,
        proposed_carrier=report_order.proposed_carrier,
        broker=user,
        created_by=report_order.created_by,
        cargo_type=report_order.cargo_type,
        equipment_type=report_order.equipment_type,
        origin=report_order.origin,
        destination=report_order.destination,
        pickup_date=report_order.pickup_date,
        delivery_date=report_order.delivery_date,
        customer_rate=report_order.customer_rate,
        carrier_cost=report_order.carrier_cost,
        number="ORD-REPORT-003",
    )
    Commission.objects.create(
        order=second_order,
        broker=user,
        rule=rule,
        gross_profit_usd=Decimal("200"),
        commission_rate=Decimal("10"),
        gross_commission_usd=Decimal("20"),
        commission_amount_usd=Decimal("20"),
        calculated_by=user,
        status=CommissionStatus.AUTHORIZED,
        authorized_by=user,
        authorized_at=timezone.now(),
    )
    debt = BrokerDebt.objects.create(
        broker=user,
        origin_commission=first_commission,
        loss_report="Informe ficticio de pérdida.",
        negotiation_agreement="Acuerdo ficticio.",
        loss_amount_usd=Decimal("3.00"),
        company_covered_loss_usd=Decimal("0.00"),
        agreed_amount_usd=Decimal("3.00"),
        balance_usd=Decimal("3.00"),
        responsibility_percentage=Decimal("100.00"),
        approved_by=user,
    )
    CommissionDebtApplication.objects.create(
        debt=debt,
        commission=first_commission,
        amount_usd=Decimal("3.00"),
        applied_by=user,
    )
    manager = get_user_model().objects.create_user(
        username="commission-summary-manager", password="test-pass-123"
    )
    manager.groups.add(Group.objects.get(name="Gerente general"))
    manager.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order"),
        *Permission.objects.filter(
            content_type__app_label="finance", codename="view_financialtransaction"
        ),
    )
    client.force_login(manager)

    summary = client.get(reverse("reports:detail", args=["commissions"]))
    broker_id = summary.context["rows"][0]["broker_id"]
    details = client.get(
        reverse("reports:detail", args=["commissions"]), {"broker": broker_id}
    )

    assert summary.status_code == 200
    assert summary.context["commission_detail_mode"] is False
    assert summary.context["rows"][0]["order_count"] == 2
    assert summary.context["rows"][0]["commission_total_usd"] == Decimal("30.00")
    assert summary.context["rows"][0]["applied_debt_total_usd"] == Decimal("3.00")
    assert summary.context["rows"][0]["payable_total_usd"] == Decimal("27.00")
    assert details.status_code == 200
    assert details.context["commission_detail_mode"] is True
    assert {row.order_id for row in details.context["rows"]} == {
        report_order.pk,
        second_order.pk,
    }


@pytest.mark.django_db
def test_financial_report_is_not_available_to_broker(client, report_order):
    user = report_order.broker
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    assert client.get(reverse("reports:detail", args=["commissions"])).status_code == 403


@pytest.mark.django_db
def test_report_page_size_comes_from_configuration(db):
    SystemConfiguration.objects.update_or_create(
        key="report-page-size", defaults={"value": "40", "is_active": True}
    )

    assert report_page_size() == 40


@pytest.mark.django_db
def test_broker_cannot_export_report(client, report_order):
    user = report_order.broker
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    assert client.get(
        reverse("reports:detail", args=["orders-status"]), {"format": "csv"}
    ).status_code == 403


@pytest.mark.django_db
def test_manager_can_export_operational_report(client, report_order):
    manager = get_user_model().objects.create_user(
        username="report-manager", password="test-pass-123"
    )
    manager.groups.add(Group.objects.get(name="Gerente general"))
    manager.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(manager)

    response = client.get(
        reverse("reports:detail", args=["orders-status"]), {"format": "csv"}
    )

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")


@pytest.mark.django_db
def test_users_report_requires_user_view_permission(client):
    user = get_user_model().objects.create_user(username="users-report-denied")

    response = client.get(reverse("reports:detail", args=["users"]))

    assert response.status_code == 302
    client.force_login(user)
    response = client.get(reverse("reports:detail", args=["users"]))
    assert response.status_code == 403


@pytest.mark.django_db
def test_users_report_filters_inactive_accounts_and_roles(client):
    user_model = get_user_model()
    report_viewer = user_model.objects.create_user(username="users-report-viewer")
    view_users = Permission.objects.get(content_type__app_label="auth", codename="view_user")
    report_viewer.user_permissions.add(view_users)
    inactive_user = user_model.objects.create_user(
        username="historical-broker", is_active=False, first_name="Demo"
    )
    inactive_user.groups.add(Group.objects.get(name="Broker"))
    user_model.objects.create_user(username="active-dispatcher")
    client.force_login(report_viewer)

    response = client.get(
        reverse("reports:detail", args=["users"]),
        {
            "is_active": "inactive",
            "group": Group.objects.get(name="Broker").pk,
            "date_from": timezone.localtime(inactive_user.date_joined).date(),
            "date_to": timezone.localtime(inactive_user.date_joined).date(),
        },
    )

    assert response.status_code == 200
    assert list(response.context["rows"]) == [inactive_user]
    assert "historical-broker" in response.content.decode()
    assert "active-dispatcher" not in response.content.decode()
    assert client.get(
        reverse("reports:detail", args=["users"]), {"format": "csv"}
    ).status_code == 403


@pytest.mark.django_db
def test_customer_report_exports_are_audited_and_csv_formula_values_are_safe(client):
    from apps.customers.models import Customer

    manager = get_user_model().objects.create_user(username="customer-report-manager")
    manager.groups.add(Group.objects.get(name="Gerente administrativo"))
    manager.user_permissions.add(
        Permission.objects.get(content_type__app_label="customers", codename="view_customer")
    )
    customer = Customer.objects.create(
        nit="CSV001",
        legal_name=" =1+1 Cliente Reporte Secreto",
        city="Guatemala",
        created_by=manager,
    )
    client.force_login(manager)

    response = client.get(
        reverse("reports:detail", args=["customers"]),
        {
            "query": "Secreto",
            "is_active": "active",
            "date_from": timezone.localtime(customer.created_at).date(),
            "date_to": timezone.localtime(customer.created_at).date(),
            "format": "csv",
        },
    )

    event = AuditEvent.objects.get(action="export_report", entity_id="admin-customers")
    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "' =1+1 Cliente Reporte Secreto" in response.content.decode()
    assert event.metadata["search_used"] is True
    assert "Secreto" not in str(event.metadata)


@pytest.mark.django_db
def test_carrier_and_incident_reports_filter_current_historical_states(
    client, report_order
):
    carrier = report_order.proposed_carrier
    carrier.is_active = False
    carrier.is_validated = False
    carrier.save()
    carrier_viewer = get_user_model().objects.create_user(username="carrier-report-viewer")
    carrier_viewer.groups.add(Group.objects.get(name="Gerente general"))
    carrier_viewer.user_permissions.add(
        Permission.objects.get(content_type__app_label="carriers", codename="view_carrier")
    )
    client.force_login(carrier_viewer)
    carrier_response = client.get(
        reverse("reports:detail", args=["carriers"]),
        {
            "is_active": "inactive",
            "is_validated": "no",
            "date_from": timezone.localtime(carrier.created_at).date(),
            "date_to": timezone.localtime(carrier.created_at).date(),
        },
    )

    incident_viewer = get_user_model().objects.create_user(username="incident-report-viewer")
    incident_viewer.groups.add(Group.objects.get(name="Gerente general"))
    incident_viewer.user_permissions.add(
        Permission.objects.get(content_type__app_label="incidents", codename="view_incident")
    )
    incident = Incident.objects.create(
        order=report_order,
        incident_type=CatalogEntry.objects.get(code="retraso-en-entrega"),
        priority=CatalogEntry.objects.get(code="critica"),
        title="Incidencia para reporte administrativo",
        description="Registro ficticio para pruebas de reporte.",
        created_by=incident_viewer,
    )
    client.force_login(incident_viewer)
    incident_response = client.get(
        reverse("reports:detail", args=["incidents"]),
        {
            "incident_status": "open",
            "priority": incident.priority_id,
            "date_from": timezone.localtime(incident.created_at).date(),
            "date_to": timezone.localtime(incident.created_at).date(),
        },
    )

    assert carrier_response.status_code == 200
    assert list(carrier_response.context["rows"]) == [carrier]
    assert incident_response.status_code == 200
    assert list(incident_response.context["rows"]) == [incident]


@pytest.mark.django_db
def test_incident_report_requires_incident_view_permission(client):
    user = get_user_model().objects.create_user(username="incident-report-denied")
    client.force_login(user)

    response = client.get(reverse("reports:detail", args=["incidents"]))

    assert response.status_code == 403

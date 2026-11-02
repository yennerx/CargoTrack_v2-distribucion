from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer
from apps.finance.models import FinancialStatus, FinancialTransaction
from apps.orders.models import Order

from .forms import CarrierForm
from .models import Carrier, CarrierDocument, CarrierType, CarrierUnit
from .services import document_is_expiring_soon, validate_carrier


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="carriers", codename__in=codenames)
    )


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="operator", password="test-pass-123")


@pytest.fixture
def carrier(user):
    return Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="1234-5",
        legal_name="Transportes Demo",
        primary_phone="5555-5555",
        email="contacto@example.com",
        created_by=user,
    )


@pytest.mark.django_db
def test_carrier_requires_and_normalizes_nit():
    form = CarrierForm(
        data={
            "carrier_type": CarrierType.COMPANY,
            "nit": " 1234-5 ",
            "legal_name": "Transportes Demo",
            "primary_phone": "5555-5555",
            "email": "contacto@example.com",
        }
    )

    assert form.is_valid()
    assert form.cleaned_data["nit"] == "12345"
    assert not CarrierForm(data={"carrier_type": CarrierType.COMPANY}).is_valid()


@pytest.mark.django_db
def test_active_license_plate_is_unique(user, carrier):
    equipment = CatalogEntry.objects.filter(catalog_type=CatalogType.EQUIPMENT_TYPE).first()
    CarrierUnit.objects.create(
        carrier=carrier,
        equipment_type=equipment,
        unit_identifier="UNIT-01",
        license_plate="P-123ABC",
    )

    with pytest.raises(IntegrityError):
        CarrierUnit.objects.create(
            carrier=carrier,
            equipment_type=equipment,
            unit_identifier="UNIT-02",
            license_plate="P-123ABC",
        )


@pytest.mark.django_db
def test_expiring_document_is_detected(carrier):
    document_type = CatalogEntry.objects.get(code="licencia")
    document = CarrierDocument.objects.create(
        carrier=carrier,
        document_type=document_type,
        document_number="LIC-001",
        expires_at=date.today() + timedelta(days=30),
    )

    assert document_is_expiring_soon(document)


@pytest.mark.django_db
def test_carrier_validation_requires_all_current_documents(carrier, user):
    with pytest.raises(ValidationError):
        validate_carrier(carrier, user)


@pytest.mark.django_db
def test_carrier_validation_records_dispatcher_and_documents(carrier, user):
    for code in ("licencia", "seguro", "tarjeta-de-circulacion", "permiso"):
        CarrierDocument.objects.create(
            carrier=carrier,
            document_type=CatalogEntry.objects.get(code=code),
            document_number=f"DOC-{code}",
            expires_at=date.today() + timedelta(days=90),
        )

    validate_carrier(carrier, user)
    carrier.refresh_from_db()

    assert carrier.is_validated
    assert carrier.validated_by == user
    assert carrier.documents.filter(is_validated=True).count() == 4


@pytest.mark.django_db
def test_broker_can_consult_but_not_modify_carrier(client, user, carrier):
    grant(user, "view_carrier")
    client.force_login(user)

    assert client.get(reverse("carriers:detail", args=[carrier.pk])).status_code == 200
    assert client.get(reverse("carriers:update", args=[carrier.pk])).status_code == 403


@pytest.mark.django_db
def test_dispatcher_can_modify_and_validate_carrier(client, user, carrier):
    grant(user, "view_carrier", "change_carrier")
    client.force_login(user)

    assert client.get(reverse("carriers:update", args=[carrier.pk])).status_code == 200


@pytest.mark.django_db
def test_carrier_deactivation_requires_delete_permission(client, user, carrier):
    grant(user, "delete_carrier")
    client.force_login(user)

    response = client.post(reverse("carriers:deactivate", args=[carrier.pk]))

    assert response.status_code == 302
    assert not Carrier.objects.get(pk=carrier.pk).is_active
    assert AuditEvent.objects.filter(
        action="deactivate_carrier",
        entity_id=str(carrier.pk),
    ).exists()


@pytest.mark.django_db
def test_broker_sees_only_created_or_assigned_carriers(client):
    broker = get_user_model().objects.create_user(username="carrier-assigned-broker")
    broker.groups.add(Group.objects.get(name="Broker"))
    creator = get_user_model().objects.create_user(username="carrier-master-creator")
    creator.groups.add(Group.objects.get(name="Administrador"))
    created_by_broker = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="CSCOPE01",
        legal_name="Creado por broker",
        primary_phone="5555",
        email="broker@example.test",
        created_by=broker,
    )
    assigned_to_broker = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="CSCOPE02",
        legal_name="Asignado al broker",
        primary_phone="5556",
        email="assigned@example.test",
        created_by=creator,
    )
    assigned_to_broker.brokers.add(broker)
    private_carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="CSCOPE03",
        legal_name="Transportista de otro broker",
        primary_phone="5557",
        email="private@example.test",
        created_by=creator,
    )
    grant(broker, "view_carrier")
    client.force_login(broker)

    response = client.get(reverse("carriers:list"))

    assert response.status_code == 200
    assert set(response.context["carriers"]) == {created_by_broker, assigned_to_broker}
    assert client.get(
        reverse("carriers:detail", args=[private_carrier.pk])
    ).status_code == 404


@pytest.mark.django_db
def test_carrier_creation_by_non_broker_requires_assignment():
    administrator = get_user_model().objects.create_user(username="carrier-form-admin")
    administrator.groups.add(Group.objects.get(name="Administrador"))
    broker = get_user_model().objects.create_user(username="carrier-form-broker")
    broker.groups.add(Group.objects.get(name="Broker"))
    fields = {
        "carrier_type": CarrierType.COMPANY,
        "nit": "CSCOPE04",
        "legal_name": "Transportista asignado",
        "primary_phone": "5558",
        "email": "assigned-carrier@example.test",
    }

    missing_assignment = CarrierForm(data=fields, actor=administrator)
    assigned = CarrierForm(
        data={**fields, "brokers": [broker.pk]}, actor=administrator
    )

    assert not missing_assignment.is_valid()
    assert "brokers" in missing_assignment.errors
    assert assigned.is_valid()


@pytest.mark.django_db
def test_administrator_create_carrier_button_is_right_aligned(client):
    administrator = get_user_model().objects.create_user(username="carrier-list-admin")
    administrator.groups.add(Group.objects.get(name="Administrador"))
    client.force_login(administrator)

    response = client.get(reverse("carriers:list"))

    assert response.status_code == 200
    assert "justify-content-between" in response.content.decode()
    assert "btn btn-primary ms-auto" in response.content.decode()


@pytest.mark.django_db
def test_carrier_detail_shows_service_and_payment_history(client, user, carrier):
    user.groups.add(Group.objects.get(name="Broker"))
    grant(user, "view_carrier")
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order"),
        Permission.objects.get(
            content_type__app_label="finance", codename="view_financialtransaction"
        ),
    )
    carrier.brokers.add(user)
    customer = Customer.objects.create(
        nit="HISTCUST01", legal_name="Cliente del servicio", created_by=user
    )
    customer.brokers.add(user)
    order = Order.objects.create(
        number="ORD-CARRIER-HISTORY",
        status=CatalogEntry.objects.get(
            catalog_type=CatalogType.ORDER_STATUS, code="solicitud-recibida"
        ),
        customer=customer,
        proposed_carrier=carrier,
        confirmed_carrier=carrier,
        broker=user,
        created_by=user,
        cargo_type=CatalogEntry.objects.filter(catalog_type=CatalogType.CARGO_TYPE).first(),
        equipment_type=CatalogEntry.objects.filter(
            catalog_type=CatalogType.EQUIPMENT_TYPE
        ).first(),
        origin="Origen",
        destination="Destino",
        pickup_date=date.today(),
        delivery_date=date.today(),
        customer_rate=Decimal("125.00"),
        carrier_cost=Decimal("100.00"),
    )
    FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(
            catalog_type=CatalogType.FINANCIAL_MOVEMENT, code="pago-transportista"
        ),
        cost_type=CatalogEntry.objects.get(
            catalog_type=CatalogType.COST_TYPE, code="costo-transportista"
        ),
        currency=CatalogEntry.objects.get(catalog_type=CatalogType.CURRENCY, code="usd"),
        amount=Decimal("100.00"),
        base_amount_usd=Decimal("100.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    another_broker = get_user_model().objects.create_user(username="other-carrier-history-broker")
    another_broker.groups.add(Group.objects.get(name="Broker"))
    Order.objects.create(
        number="ORD-CARRIER-PRIVATE",
        status=order.status,
        customer=customer,
        proposed_carrier=carrier,
        confirmed_carrier=carrier,
        broker=another_broker,
        created_by=another_broker,
        cargo_type=order.cargo_type,
        equipment_type=order.equipment_type,
        origin=order.origin,
        destination=order.destination,
        pickup_date=order.pickup_date,
        delivery_date=order.delivery_date,
        customer_rate=order.customer_rate,
        carrier_cost=order.carrier_cost,
    )

    client.force_login(user)
    response = client.get(reverse("carriers:detail", args=[carrier.pk]))

    assert response.status_code == 200
    assert list(response.context["orders"].object_list) == [order]
    assert "ORD-CARRIER-PRIVATE" not in response.content.decode()
    assert response.context["payments"].paginator.count == 1
    assert "ORD-CARRIER-HISTORY" in response.content.decode()
    assert response.context["can_view_payment_history"]
    assert "Historial de pagos" in response.content.decode()
    assert "USD 100,00" in response.content.decode()

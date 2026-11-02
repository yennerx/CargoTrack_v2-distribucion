from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import IntegrityError
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier, CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.finance.models import FinancialStatus, FinancialTransaction
from apps.orders.models import Order

from .forms import CustomerContactFormSet, CustomerForm
from .models import Customer, CustomerContact


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="customers",
            codename__in=codenames,
        )
    )


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="operator", password="test-pass-123")


@pytest.mark.django_db
def test_customer_requires_and_normalizes_nit():
    form = CustomerForm(data={"nit": " 1234-5 ", "legal_name": "Cliente Demo"})

    assert form.is_valid()
    assert form.cleaned_data["nit"] == "12345"

    assert not CustomerForm(data={"legal_name": "Sin NIT"}).is_valid()


@pytest.mark.django_db
def test_customer_form_has_spanish_labels_and_primary_contact_by_default():
    form = CustomerForm()
    formset = CustomerContactFormSet()

    assert form.fields["legal_name"].label == "Nombre legal"
    assert form.fields["nit"].required
    assert formset.forms[0].fields["is_primary"].initial is True


@pytest.mark.django_db
def test_customer_nit_is_unique(user):
    Customer.objects.create(nit="12345", legal_name="Primero", created_by=user)

    with pytest.raises(IntegrityError):
        Customer.objects.create(nit="12345", legal_name="Duplicado", created_by=user)


@pytest.mark.django_db
def test_customer_has_one_active_primary_contact(user):
    customer = Customer.objects.create(nit="12345", legal_name="Cliente Demo", created_by=user)
    CustomerContact.objects.create(
        customer=customer,
        name="Contacto Uno",
        primary_phone="5555-5555",
        email="uno@example.com",
        is_primary=True,
    )

    with pytest.raises(IntegrityError):
        CustomerContact.objects.create(
            customer=customer,
            name="Contacto Dos",
            primary_phone="5555-5556",
            email="dos@example.com",
            is_primary=True,
        )


@pytest.mark.django_db
def test_broker_can_create_but_not_modify_customer(client, user):
    grant(user, "view_customer", "add_customer", "add_customercontact", "view_customercontact")
    customer = Customer.objects.create(nit="12345", legal_name="Cliente Demo", created_by=user)
    client.force_login(user)

    assert client.get(reverse("customers:create")).status_code == 200
    list_response = client.get(reverse("customers:list"))
    assert "justify-content-between" in list_response.content.decode()
    assert "customer-create-button ms-auto" in list_response.content.decode()
    assert client.get(reverse("customers:update", args=[customer.pk])).status_code == 403


@pytest.mark.django_db
def test_dispatcher_can_modify_customer(client, user):
    grant(
        user,
        "view_customer",
        "change_customer",
        "view_customercontact",
        "change_customercontact",
    )
    customer = Customer.objects.create(nit="12345", legal_name="Cliente Demo", created_by=user)
    client.force_login(user)

    assert client.get(reverse("customers:update", args=[customer.pk])).status_code == 200


@pytest.mark.django_db
def test_customer_updated_at_is_automatic(user):
    customer = Customer.objects.create(nit="12345", legal_name="Cliente Demo", created_by=user)
    original_updated_at = customer.updated_at
    customer.legal_name = "Cliente Actualizado"
    customer.save()

    assert customer.updated_at >= original_updated_at


@pytest.mark.django_db
def test_customer_deactivation_is_audited(client, user):
    grant(user, "view_customer", "change_customer")
    customer = Customer.objects.create(nit="12345", legal_name="Cliente Demo", created_by=user)
    client.force_login(user)

    response = client.post(reverse("customers:deactivate", args=[customer.pk]))

    assert response.status_code == 302
    assert not Customer.objects.get(pk=customer.pk).is_active
    assert AuditEvent.objects.filter(
        action="deactivate_customer",
        entity_type="customer",
        entity_id=str(customer.pk),
    ).exists()


@pytest.mark.django_db
def test_broker_sees_only_created_or_assigned_customers(client):
    broker = get_user_model().objects.create_user(username="assigned-broker")
    broker.groups.add(Group.objects.get(name="Broker"))
    creator = get_user_model().objects.create_user(username="master-creator")
    creator.groups.add(Group.objects.get(name="Administrador"))
    created_by_broker = Customer.objects.create(
        nit="SCOPE001", legal_name="Creado por broker", created_by=broker
    )
    assigned_to_broker = Customer.objects.create(
        nit="SCOPE002", legal_name="Asignado al broker", created_by=creator
    )
    assigned_to_broker.brokers.add(broker)
    private_customer = Customer.objects.create(
        nit="SCOPE003", legal_name="Cliente de otro broker", created_by=creator
    )
    grant(broker, "view_customer")
    client.force_login(broker)

    response = client.get(reverse("customers:list"))

    assert response.status_code == 200
    assert set(response.context["customers"]) == {created_by_broker, assigned_to_broker}
    assert client.get(
        reverse("customers:detail", args=[private_customer.pk])
    ).status_code == 404


@pytest.mark.django_db
def test_broker_creation_form_uses_self_assignment_and_staff_must_select_brokers():
    from .forms import CustomerForm

    broker = get_user_model().objects.create_user(username="customer-form-broker")
    broker.groups.add(Group.objects.get(name="Broker"))
    administrator = get_user_model().objects.create_user(username="customer-form-admin")
    administrator.groups.add(Group.objects.get(name="Administrador"))

    broker_form = CustomerForm(actor=broker)
    missing_assignment = CustomerForm(
        data={"nit": "FORM001", "legal_name": "Cliente sin broker"},
        actor=administrator,
    )
    assigned_form = CustomerForm(
        data={
            "nit": "FORM002",
            "legal_name": "Cliente asignado",
            "brokers": [broker.pk],
        },
        actor=administrator,
    )

    assert "brokers" not in broker_form.fields
    assert not missing_assignment.is_valid()
    assert "brokers" in missing_assignment.errors
    assert assigned_form.is_valid()


@pytest.mark.django_db
def test_broker_created_customer_is_assigned_to_creator(client, user):
    grant(user, "add_customer")
    user.groups.add(Group.objects.get(name="Broker"))
    client.force_login(user)
    prefix = CustomerContactFormSet.get_default_prefix()
    data = {
        "nit": "AUTOBROKER01",
        "legal_name": "Cliente del broker",
        f"{prefix}-TOTAL_FORMS": "1",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-name": "Contacto de prueba",
        f"{prefix}-0-position": "Compras",
        f"{prefix}-0-primary_phone": "5555",
        f"{prefix}-0-secondary_phone": "",
        f"{prefix}-0-email": "contacto@example.test",
        f"{prefix}-0-preferred_contact_method": "Correo",
        f"{prefix}-0-is_primary": "on",
        f"{prefix}-0-is_active": "on",
    }

    response = client.post(reverse("customers:create"), data)

    customer = Customer.objects.get(nit="AUTOBROKER01")
    assert response.status_code == 302
    assert list(customer.brokers.all()) == [user]


@pytest.mark.django_db
def test_administrator_created_customer_uses_selected_broker(client):
    administrator = get_user_model().objects.create_user(username="customer-creator-admin")
    administrator.groups.add(Group.objects.get(name="Administrador"))
    broker = get_user_model().objects.create_user(username="customer-selected-broker")
    broker.groups.add(Group.objects.get(name="Broker"))
    prefix = CustomerContactFormSet.get_default_prefix()
    data = {
        "nit": "ADMINBROKER01",
        "legal_name": "Cliente asignado por administrador",
        "brokers": [str(broker.pk)],
        f"{prefix}-TOTAL_FORMS": "1",
        f"{prefix}-INITIAL_FORMS": "0",
        f"{prefix}-MIN_NUM_FORMS": "0",
        f"{prefix}-MAX_NUM_FORMS": "1000",
        f"{prefix}-0-name": "Contacto de prueba",
        f"{prefix}-0-position": "Compras",
        f"{prefix}-0-primary_phone": "5555",
        f"{prefix}-0-secondary_phone": "",
        f"{prefix}-0-email": "admin-contact@example.test",
        f"{prefix}-0-preferred_contact_method": "Correo",
        f"{prefix}-0-is_primary": "on",
        f"{prefix}-0-is_active": "on",
    }
    client.force_login(administrator)

    response = client.post(reverse("customers:create"), data)

    customer = Customer.objects.get(nit="ADMINBROKER01")
    assert response.status_code == 302
    assert list(customer.brokers.all()) == [broker]


@pytest.mark.django_db
def test_customer_detail_shows_service_and_permitted_collection_history(client, user):
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="customers", codename="view_customer"),
        Permission.objects.get(content_type__app_label="orders", codename="view_order"),
        Permission.objects.get(
            content_type__app_label="finance", codename="view_financialtransaction"
        ),
    )
    customer = Customer.objects.create(
        nit="HISTORY001", legal_name="Cliente histórico", created_by=user
    )
    customer.brokers.add(user)
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="HISTORYC01",
        legal_name="Transportista histórico",
        primary_phone="5555",
        email="carrier@example.test",
        created_by=user,
    )
    carrier.brokers.add(user)
    order = Order.objects.create(
        number="ORD-CUSTOMER-HISTORY",
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
            catalog_type=CatalogType.FINANCIAL_MOVEMENT, code="cobro-cliente"
        ),
        currency=CatalogEntry.objects.get(catalog_type=CatalogType.CURRENCY, code="usd"),
        amount=Decimal("125.00"),
        base_amount_usd=Decimal("125.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    another_broker = get_user_model().objects.create_user(username="other-history-broker")
    another_broker.groups.add(Group.objects.get(name="Broker"))
    Order.objects.create(
        number="ORD-CUSTOMER-PRIVATE",
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
    response = client.get(reverse("customers:detail", args=[customer.pk]))

    assert response.status_code == 200
    assert list(response.context["orders"].object_list) == [order]
    assert "ORD-CUSTOMER-PRIVATE" not in response.content.decode()
    assert response.context["collections"].paginator.count == 1
    assert "ORD-CUSTOMER-HISTORY" in response.content.decode()
    assert response.context["can_view_collection_history"]
    assert "Historial de cobros" in response.content.decode()
    assert "USD 125,00" in response.content.decode()

    user.user_permissions.remove(
        Permission.objects.get(
            content_type__app_label="finance", codename="view_financialtransaction"
        )
    )
    user.groups.remove(Group.objects.get(name="Broker"))
    response = client.get(reverse("customers:detail", args=[customer.pk]))

    assert response.context["collections"] is None
    assert "USD 125,00" not in response.content.decode()

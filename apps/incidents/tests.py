from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier, CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer
from apps.documents.services import upload_document
from apps.orders.models import Order

from .models import Incident, IncidentHistory, IncidentStatus


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="incidents", codename__in=codenames)
    )


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="incident-user", password="test-pass-123")


@pytest.fixture
def order(user):
    customer = Customer.objects.create(
        nit="INC001", legal_name="Cliente Incidencias", created_by=user
    )
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="INC002",
        legal_name="Transportes Incidencias",
        primary_phone="5555",
        email="incident@example.com",
        created_by=user,
    )
    return Order.objects.create(
        status=CatalogEntry.objects.get(code="solicitud-recibida"),
        customer=customer,
        proposed_carrier=carrier,
        broker=user,
        created_by=user,
        cargo_type=CatalogEntry.objects.filter(catalog_type=CatalogType.CARGO_TYPE).first(),
        equipment_type=CatalogEntry.objects.filter(catalog_type=CatalogType.EQUIPMENT_TYPE).first(),
        origin="Origen",
        destination="Destino",
        pickup_date=date.today(),
        delivery_date=date.today() + timedelta(days=2),
        customer_rate=Decimal("100.00"),
        carrier_cost=Decimal("80.00"),
        number="ORD-2026-000099",
    )


def incident_data():
    return {
        "incident_type": CatalogEntry.objects.filter(
            catalog_type=CatalogType.INCIDENT_TYPE, is_active=True
        ).first().pk,
        "priority": CatalogEntry.objects.filter(
            catalog_type=CatalogType.INCIDENT_PRIORITY, is_active=True
        ).first().pk,
        "title": "Retraso en ruta",
        "description": "La unidad reportó un retraso operativo.",
    }


@pytest.mark.django_db
def test_create_incident_records_initial_history(client, user, order):
    grant(user, "add_incident", "view_incident")
    client.force_login(user)

    response = client.post(reverse("incidents:create", args=[order.pk]), incident_data())

    incident = Incident.objects.get()
    assert response.status_code == 302
    assert incident.order == order
    assert incident.status == IncidentStatus.OPEN
    assert IncidentHistory.objects.filter(incident=incident, status=IncidentStatus.OPEN).exists()


@pytest.mark.django_db
def test_broker_incidents_follow_current_order_assignment_only(client, user, order):
    grant(user, "add_incident", "view_incident")
    user.groups.add(Group.objects.get(name="Broker"))
    other_broker = get_user_model().objects.create_user(username="incident-other-broker")
    other_broker.groups.add(Group.objects.get(name="Broker"))
    other_order = Order.objects.create(
        status=order.status,
        customer=order.customer,
        proposed_carrier=order.proposed_carrier,
        broker=other_broker,
        created_by=user,
        cargo_type=order.cargo_type,
        equipment_type=order.equipment_type,
        origin=order.origin,
        destination=order.destination,
        pickup_date=order.pickup_date,
        delivery_date=order.delivery_date,
        customer_rate=order.customer_rate,
        carrier_cost=order.carrier_cost,
        number="ORD-INC-OTHER-01",
    )
    own_incident = Incident.objects.create(
        order=order,
        incident_type=CatalogEntry.objects.get(code="retraso-en-entrega"),
        priority=CatalogEntry.objects.get(code="alta"),
        title="Incidencia asignada",
        description="Debe aparecer para el broker asignado.",
        created_by=user,
    )
    private_incident = Incident.objects.create(
        order=other_order,
        incident_type=CatalogEntry.objects.get(code="retraso-en-entrega"),
        priority=CatalogEntry.objects.get(code="alta"),
        title="Incidencia de otro broker",
        description="No debe aparecer aunque la orden la haya creado este broker.",
        created_by=user,
    )
    client.force_login(user)

    response = client.get(reverse("incidents:list"))

    assert list(response.context["incidents"]) == [own_incident]
    assert client.get(
        reverse("incidents:detail", args=[private_incident.pk])
    ).status_code == 404
    assert client.get(
        reverse("incidents:create", args=[other_order.pk])
    ).status_code == 404


@pytest.mark.django_db
def test_incident_cannot_resolve_without_resolution(client, user, order):
    grant(user, "add_incident", "view_incident", "change_incident")
    client.force_login(user)
    client.post(reverse("incidents:create", args=[order.pk]), incident_data())
    incident = Incident.objects.get()
    create_event = AuditEvent.objects.get(
        action="create_incident", entity_id=str(incident.pk)
    )
    assert create_event.order == order

    client.post(
        reverse("incidents:transition", args=[incident.pk]),
        {"status": IncidentStatus.RESOLVED, "observation": "Se revisó el caso."},
    )

    incident.refresh_from_db()
    assert incident.status == IncidentStatus.OPEN


@pytest.mark.django_db
def test_only_dispatcher_can_close_incident(client, user, order):
    grant(user, "add_incident", "view_incident", "change_incident")
    client.force_login(user)
    client.post(reverse("incidents:create", args=[order.pk]), incident_data())
    incident = Incident.objects.get()
    Incident.objects.filter(pk=incident.pk).update(
        status=IncidentStatus.RESOLVED, resolution="Resuelto"
    )
    incident.refresh_from_db()

    client.post(
        reverse("incidents:transition", args=[incident.pk]),
        {
            "status": IncidentStatus.CLOSED,
            "observation": "Cierre operativo.",
            "resolution": "Resuelto y documentado.",
        },
    )
    assert Incident.objects.get(pk=incident.pk).status == IncidentStatus.RESOLVED

    user.groups.add(Group.objects.get(name="Dispatcher"))
    client.post(
        reverse("incidents:transition", args=[incident.pk]),
        {
            "status": IncidentStatus.CLOSED,
            "observation": "Cierre validado.",
            "resolution": "Resuelto y documentado.",
        },
    )
    assert Incident.objects.get(pk=incident.pk).status == IncidentStatus.CLOSED


@pytest.mark.django_db
def test_incident_accepts_document_evidence(user, order, settings, tmp_path):
    settings.MEDIA_ROOT = Path(tmp_path)
    incident = Incident.objects.create(
        order=order,
        incident_type=CatalogEntry.objects.filter(catalog_type=CatalogType.INCIDENT_TYPE).first(),
        priority=CatalogEntry.objects.filter(catalog_type=CatalogType.INCIDENT_PRIORITY).first(),
        title="Evidencia",
        description="Incidencia con evidencia.",
        created_by=user,
    )
    document_type = CatalogEntry.objects.get(code="recibo", catalog_type=CatalogType.DOCUMENT_TYPE)

    document = upload_document(
        uploaded_file=SimpleUploadedFile("evidencia.pdf", b"%PDF-1.7 evidencia"),
        actor=user,
        target=incident,
        document_data={"document_type": document_type, "target_type": "incident"},
    )

    assert document.incident == incident
    assert document.versions.count() == 1


@pytest.mark.django_db
def test_incident_list_combines_priority_and_open_critical_alert(client, user, order):
    grant(user, "view_incident")
    incident = Incident.objects.create(
        order=order,
        incident_type=CatalogEntry.objects.filter(catalog_type=CatalogType.INCIDENT_TYPE).first(),
        priority=CatalogEntry.objects.get(
            catalog_type=CatalogType.INCIDENT_PRIORITY, code="critica"
        ),
        title="Incidente crítico visible",
        description="Requiere atención.",
        created_by=user,
    )
    client.force_login(user)

    response = client.get(reverse("incidents:list"))
    content = response.content.decode()
    priority_cell = (
        f'<td>{incident.priority.name}<span class="badge text-bg-danger ms-1">'
        "Crítica abierta</span></td>"
    )

    assert response.status_code == 200
    assert "Prioridad / criticidad" in content
    assert priority_cell in content
    assert incident.priority.name in content

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier, CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer
from apps.orders.models import Order

from .forms import DocumentUploadForm
from .services import upload_document, upload_version


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="documents", codename__in=codenames)
    )


def pdf_file(name="factura.pdf", content=b"%PDF-1.7 demo"):
    return SimpleUploadedFile(name, content, content_type="application/pdf")


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="broker-docs", password="test-pass-123")


@pytest.fixture
def carrier(user):
    return Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="DOCS001",
        legal_name="Transportes Documentales",
        primary_phone="5555",
        email="docs@example.com",
        created_by=user,
    )


@pytest.fixture
def document_type(db):
    return CatalogEntry.objects.filter(
        catalog_type=CatalogType.DOCUMENT_TYPE, is_active=True
    ).first()


def document_data(document_type):
    return {"document_type": document_type, "target_type": "carrier"}


@pytest.mark.django_db
def test_document_form_rejects_invalid_signature(document_type):
    form = DocumentUploadForm(
        data={"document_type": document_type.pk},
        files={"file": SimpleUploadedFile("evidencia.pdf", b"not-a-pdf")},
    )

    assert not form.is_valid()
    assert "file" in form.errors


@pytest.mark.django_db
def test_upload_renames_file_and_preserves_original_name(
    user, carrier, document_type, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    document = upload_document(
        uploaded_file=pdf_file("factura_cliente.pdf"),
        actor=user,
        target=carrier,
        document_data=document_data(document_type),
    )
    version = document.versions.get()

    assert version.original_name == "factura_cliente.pdf"
    assert version.stored_name == "ATT-00000001.pdf"
    assert version.is_current
    assert version.file.name.endswith(f"transportistas/{carrier.pk}/ATT-00000001.pdf")
    assert Path(version.file.path).exists()
    assert AuditEvent.objects.filter(action="upload_document").exists()


@pytest.mark.django_db
def test_new_version_can_be_restored_and_non_admin_cannot_delete(
    user, carrier, document_type, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    document = upload_document(
        uploaded_file=pdf_file(),
        actor=user,
        target=carrier,
        document_data=document_data(document_type),
    )
    grant(user, "add_documentversion", "view_document", "change_documentversion")
    second = upload_version(document=document, uploaded_file=pdf_file("v2.pdf"), actor=user)
    first = document.versions.get(version=1)

    assert second.is_current
    assert not first.is_current

    response = Client()
    response.force_login(user)
    restore_response = response.post(reverse("documents:restore", args=[first.pk]))

    assert restore_response.status_code == 403


@pytest.mark.django_db
def test_administrator_can_restore_delete_and_download_document_version(
    user, carrier, document_type, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    document = upload_document(
        uploaded_file=pdf_file(),
        actor=user,
        target=carrier,
        document_data=document_data(document_type),
    )
    grant(user, "add_documentversion")
    second = upload_version(document=document, uploaded_file=pdf_file("v2.pdf"), actor=user)
    administrator = get_user_model().objects.create_user(
        username="administrator-docs", password="test-pass-123"
    )
    administrator.groups.add(Group.objects.get(name="Administrador"))
    client = Client()
    client.force_login(administrator)

    restore_response = client.post(
        reverse("documents:restore", args=[document.versions.get(version=1).pk])
    )
    download_response = client.get(reverse("documents:download", args=[second.pk]))
    delete_response = client.post(reverse("documents:delete", args=[second.pk]))

    assert restore_response.status_code == 302
    assert download_response.status_code == 200
    assert delete_response.status_code == 302
    second.refresh_from_db()
    assert second.is_deleted
    assert AuditEvent.objects.filter(action="download_document_version").exists()
    assert AuditEvent.objects.filter(action="delete_document_version").exists()


@pytest.mark.django_db
def test_broker_cannot_open_or_download_documents_of_unassigned_carriers(
    user, carrier, document_type, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    user.groups.add(Group.objects.get(name="Broker"))
    grant(user, "view_document")
    administrator = get_user_model().objects.create_user(username="other-carrier-creator")
    administrator.groups.add(Group.objects.get(name="Administrador"))
    private_carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="DOCS002",
        legal_name="Transportista privado",
        primary_phone="5556",
        email="private-docs@example.test",
        created_by=administrator,
    )
    own_document = upload_document(
        uploaded_file=pdf_file("propio.pdf"),
        actor=user,
        target=carrier,
        document_data=document_data(document_type),
    )
    private_document = upload_document(
        uploaded_file=pdf_file("privado.pdf"),
        actor=administrator,
        target=private_carrier,
        document_data=document_data(document_type),
    )
    client = Client()
    client.force_login(user)

    assert client.get(reverse("documents:detail", args=[own_document.pk])).status_code == 200
    assert client.get(
        reverse("documents:detail", args=[private_document.pk])
    ).status_code == 404
    assert client.get(
        reverse("documents:download", args=[private_document.versions.get().pk])
    ).status_code == 404


@pytest.mark.django_db
def test_order_document_audit_event_is_linked_to_its_order(
    user, carrier, document_type, settings, tmp_path
):
    settings.MEDIA_ROOT = Path(tmp_path)
    customer = Customer.objects.create(
        nit="AUDITDOC01", legal_name="Cliente documental", created_by=user
    )
    order = Order.objects.create(
        number="ORD-DOC-AUDIT-01",
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
    upload_document(
        uploaded_file=pdf_file("factura_privada.pdf"),
        actor=user,
        target=order,
        document_data={"document_type": document_type, "target_type": "order"},
    )

    event = AuditEvent.objects.get(action="upload_document")
    assert event.order == order
    assert "original_name" not in event.metadata
    assert "stored_name" not in event.metadata

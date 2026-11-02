import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import RequestFactory

from apps.audit.models import AuditEvent

from .admin import CatalogEntryAdmin
from .models import CatalogEntry, CatalogType


@pytest.mark.django_db
def test_catalog_admin_changes_are_audited():
    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="test-pass-123",
    )
    request = RequestFactory().post("/admin/catalogs/catalogentry/add/")
    request.user = user
    entry = CatalogEntry(
        catalog_type=CatalogType.INCIDENT_TYPE,
        code="incidencia-prueba",
        name="Incidencia de prueba",
    )

    CatalogEntryAdmin(CatalogEntry, AdminSite()).save_model(request, entry, None, False)

    event = AuditEvent.objects.get(entity_type="catalog_entry", entity_id=str(entry.pk))
    assert event.actor == user
    assert event.action == "create_catalog"


@pytest.mark.django_db
def test_catalog_admin_deletion_is_audited():
    user = get_user_model().objects.create_superuser(
        username="catalog-delete-admin",
        email="catalog-delete@example.test",
        password="test-pass-123",
    )
    entry = CatalogEntry.objects.create(
        catalog_type=CatalogType.INCIDENT_TYPE,
        code="audit-deletion-test",
        name="Catálogo de eliminación",
    )
    request = RequestFactory().post("/admin/catalogs/catalogentry/")
    request.user = user
    entry_id = str(entry.pk)

    CatalogEntryAdmin(CatalogEntry, AdminSite()).delete_model(request, entry)

    event = AuditEvent.objects.get(
        action="delete_catalog", entity_type="catalog_entry", entity_id=entry_id
    )
    assert event.actor == user
    assert event.metadata == {
        "catalog_type": CatalogType.INCIDENT_TYPE,
        "code": "audit-deletion-test",
    }

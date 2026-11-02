import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse

from .models import CatalogEntry, CatalogType, SystemConfiguration


@pytest.mark.django_db
def test_approved_initial_catalogs_are_loaded():
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.ORDER_STATUS).count() == 12
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.DOCUMENT_TYPE).count() == 9
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.CARGO_TYPE).count() == 7
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.EQUIPMENT_TYPE).count() == 7
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.INCIDENT_TYPE).count() == 7
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.INCIDENT_PRIORITY).count() == 4
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.FINANCIAL_MOVEMENT).count() == 5
    assert CatalogEntry.objects.filter(catalog_type=CatalogType.EXPENSE_TYPE).count() == 7
    assert SystemConfiguration.objects.get(key="operating-currency").value == "USD"


@pytest.mark.django_db
def test_catalog_code_is_unique_within_catalog_type():
    entry = CatalogEntry.objects.get(catalog_type=CatalogType.DOCUMENT_TYPE, code="factura")

    with pytest.raises(IntegrityError):
        CatalogEntry.objects.create(
            catalog_type=CatalogType.DOCUMENT_TYPE,
            code=entry.code,
            name="Factura duplicada",
        )


@pytest.mark.django_db
def test_catalog_dashboard_requires_view_permission(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    client.force_login(user)

    response = client.get(reverse("catalogs:dashboard"))

    assert response.status_code == 403


@pytest.mark.django_db
def test_catalog_dashboard_is_available_to_superuser(client):
    user_model = get_user_model()
    user = user_model.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="test-pass-123",
    )
    client.force_login(user)

    response = client.get(reverse("catalogs:dashboard"))

    assert response.status_code == 200
    assert "Configuración y catálogos" in response.content.decode()
    assert "USD" in response.content.decode()

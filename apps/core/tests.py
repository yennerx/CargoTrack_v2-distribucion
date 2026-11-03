import json

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.staticfiles import finders
from django.urls import reverse

from .models import UserDashboardPreference, UserNavigationPreference


@pytest.mark.django_db
def test_health_check(client):
    response = client.get(reverse("core:health-check"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "cargotrack"}


@pytest.mark.django_db
def test_home_uses_base_template(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    client.force_login(user)

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert "CargoTrack" in response.content.decode()
    assert "htmx" in response.content.decode().lower()
    assert "Resumen de CargoTrack" in response.content.decode()
    assert "Accesos autorizados" not in response.content.decode()
    assert "Módulos de CargoTrack" not in response.content.decode()


@pytest.mark.django_db
def test_authenticated_user_sees_visual_module_navigation(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="customers", codename="view_customer")
    )
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="carriers", codename="view_carrier")
    )
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    response = client.get(reverse("core:home"))
    content = response.content.decode()

    assert "Clientes" in content
    assert "Transportistas" in content
    assert "Órdenes" in content
    assert "Comisiones" not in content
    assert "Auditoría" not in content
    assert "sidebar-section-toggle" in content
    assert "sidebar-section-" in content
    assert reverse("orders:list") in content


@pytest.mark.django_db
def test_audit_placeholder_requires_audit_permission(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    client.force_login(user)

    response = client.get(reverse("core:module-placeholder", args=["auditoria"]))

    assert response.status_code == 403


@pytest.mark.django_db
def test_authorized_manager_sees_commissions_and_audit_links(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="manager", password="test-pass-123")
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label__in=("finance", "audit"),
            codename__in=("view_commission", "view_auditevent"),
        )
    )
    client.force_login(user)

    response = client.get(reverse("core:home"))
    content = response.content.decode()

    assert "Comisiones" in content
    assert reverse("finance:commission-list") in content
    assert "Auditoría" in content
    assert reverse("audit:list") in content


@pytest.mark.django_db
def test_navigation_defaults_to_expanded_and_marks_create_route_active(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="customer-user", password="test-pass-123")
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="customers",
            codename__in=("view_customer", "add_customer"),
        )
    )
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    response = client.get(reverse("customers:create"))
    sections = {section["slug"]: section for section in response.context["navigation_sections"]}
    customer_item = next(
        item
        for item in sections["operacion"]["items"]
        if item["slug"] == "clientes"
    )

    assert response.status_code == 200
    assert sections["operacion"]["collapsed"] is False
    assert customer_item["active"] is True


@pytest.mark.django_db
def test_navigation_preferences_persist_for_user(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="navigation-user", password="test-pass-123")
    user.user_permissions.add(
        *Permission.objects.filter(
            content_type__app_label="customers",
            codename__in=("view_customer", "add_customer"),
        )
    )
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)

    response = client.post(
        reverse("core:save-navigation-preference"),
        data=json.dumps(
            {"collapsed_sections": ["operacion", "sistema"], "sidebar_collapsed": True}
        ),
        content_type="application/json",
    )

    preference = UserNavigationPreference.objects.get(user=user)
    assert response.status_code == 200
    assert preference.collapsed_sections == ["operacion", "sistema"]
    assert preference.sidebar_collapsed is True

    client.logout()
    client.force_login(user)
    page = client.get(reverse("customers:create"))
    sections = {section["slug"]: section for section in page.context["navigation_sections"]}
    assert sections["operacion"]["collapsed"] is True
    assert sections["control"]["collapsed"] is False
    assert page.context["sidebar_collapsed"] is True
    customer_item = next(
        item for item in sections["operacion"]["items"] if item["slug"] == "clientes"
    )
    assert customer_item["active"] is True
    assert 'href="#icon-clientes"' in page.content.decode()


@pytest.mark.django_db
def test_navigation_preference_rejects_unknown_sections(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="navigation-user", password="test-pass-123")
    client.force_login(user)

    response = client.post(
        reverse("core:save-navigation-preference"),
        data=json.dumps({"collapsed_sections": ["admin-total"], "sidebar_collapsed": False}),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserNavigationPreference.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_dashboard_defaults_are_role_based_and_financial_widgets_are_restricted(client):
    user_model = get_user_model()
    broker = user_model.objects.create_user(username="dashboard-broker", password="test-pass-123")
    broker.groups.add(Group.objects.get(name="Broker"))
    broker.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order"),
        Permission.objects.get(
            content_type__app_label="finance", codename="view_financialtransaction"
        ),
    )
    client.force_login(broker)

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert response.context["dashboard_visible_widgets"] == ["active_orders", "overdue_orders"]
    assert "Utilidad acumulada" not in response.content.decode()


@pytest.mark.django_db
def test_dashboard_preferences_persist_widget_order_and_visibility(client):
    user = get_user_model().objects.create_user(
        username="dashboard-dispatcher", password="test-pass-123"
    )
    user.groups.add(Group.objects.get(name="Dispatcher"))
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order"),
        Permission.objects.get(
            content_type__app_label="finance", codename="view_financialtransaction"
        ),
    )
    client.force_login(user)
    initial = client.get(reverse("core:home"))
    widget_order = initial.context["dashboard_widget_ids"]
    assert initial.context["dashboard_visible_widgets"] == [
        "active_orders",
        "overdue_orders",
        "pending_collections",
        "pending_payments",
    ]
    reordered = list(reversed(widget_order))
    visible = ["pending_payments", "active_orders"]

    response = client.post(
        reverse("core:save-dashboard-preference"),
        data=json.dumps({"widget_order": reordered, "visible_widgets": visible}),
        content_type="application/json",
    )

    assert response.status_code == 200
    preference = UserDashboardPreference.objects.get(user=user)
    assert preference.widget_order == reordered
    assert preference.visible_widgets == visible

    client.logout()
    client.force_login(user)
    dashboard = client.get(reverse("core:home"))
    assert dashboard.context["dashboard_widget_ids"] == reordered
    assert dashboard.context["dashboard_visible_widgets"] == visible


@pytest.mark.django_db
def test_dashboard_defaults_include_authorized_financial_widgets_for_management(client):
    manager = get_user_model().objects.create_user(
        username="dashboard-manager", password="test-pass-123"
    )
    manager.groups.add(Group.objects.get(name="Gerente administrativo"))
    client.force_login(manager)

    response = client.get(reverse("core:home"))

    assert response.status_code == 200
    assert response.context["dashboard_visible_widgets"] == [
        "active_orders",
        "overdue_orders",
        "profit_usd",
        "pending_commissions",
        "pending_debts",
    ]


@pytest.mark.django_db
def test_dashboard_preferences_reject_widgets_outside_user_permissions(client):
    user = get_user_model().objects.create_user(
        username="dashboard-limited", password="test-pass-123"
    )
    user.groups.add(Group.objects.get(name="Broker"))
    user.user_permissions.add(
        Permission.objects.get(content_type__app_label="orders", codename="view_order")
    )
    client.force_login(user)
    allowed = ["active_orders", "overdue_orders"]

    response = client.post(
        reverse("core:save-dashboard-preference"),
        data=json.dumps(
            {
                "widget_order": [*allowed, "pending_commissions"],
                "visible_widgets": ["active_orders", "pending_commissions"],
            }
        ),
        content_type="application/json",
    )

    assert response.status_code == 400
    assert not UserDashboardPreference.objects.filter(user=user).exists()


def test_static_css_is_available_in_development(client):
    static_file = finders.find("css/app.css")

    assert static_file is not None


def test_health_check_rejects_non_get_requests(client):
    response = client.post(reverse("core:health-check"))

    assert response.status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url_name,args",
    [
        ("audit:list", ()),
        ("audit:order_history", (1,)),
        ("carriers:list", ()),
        ("carriers:detail", (1,)),
        ("catalogs:dashboard", ()),
        ("core:home", ()),
        ("core:module-placeholder", ("clientes",)),
        ("customers:list", ()),
        ("customers:detail", (1,)),
        ("documents:detail", (1,)),
        ("documents:download", (1,)),
        ("finance:list", ()),
        ("finance:order", (1,)),
        ("finance:commission-list", ()),
        ("finance:commission-detail", (1,)),
        ("finance:commission-rules", ()),
        ("incidents:list", ()),
        ("incidents:detail", (1,)),
        ("orders:list", ()),
        ("orders:detail", (1,)),
        ("reports:dashboard", ()),
        ("reports:detail", ("orders",)),
    ],
)
def test_read_only_endpoints_reject_post_requests(client, url_name, args):
    user = get_user_model().objects.create_user(username="http-method-user")
    client.force_login(user)

    response = client.post(reverse(url_name, args=args))

    assert response.status_code == 405


@pytest.mark.django_db
def test_not_found_uses_centralized_error_page(client, settings):
    settings.DEBUG = False

    response = client.get("/ruta-que-no-existe/")

    assert response.status_code == 404
    assert "Página no encontrada" in response.content.decode()

import time

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from apps.audit.models import AuditEvent
from apps.catalogs.models import SystemConfiguration

from .sessions import LAST_ACTIVITY_SESSION_KEY, idle_timeout_seconds


@pytest.mark.django_db
def test_login_authenticates_active_user(client):
    user_model = get_user_model()
    user_model.objects.create_user(username="broker", password="test-pass-123")

    response = client.post(
        reverse("accounts:login"),
        {"username": "broker", "password": "test-pass-123"},
    )

    assert response.status_code == 302
    assert response.url == reverse("core:home")


@pytest.mark.django_db
def test_authenticated_user_is_redirected_from_login(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    client.force_login(user)

    response = client.get(reverse("accounts:login"))

    assert response.status_code == 302
    assert response.url == reverse("core:home")


@pytest.mark.django_db
def test_authenticated_pages_are_not_cacheable(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    client.force_login(user)

    response = client.get(reverse("core:home"))

    assert response.headers["Cache-Control"] == "no-store, no-cache, must-revalidate, max-age=0"
    assert response.headers["Pragma"] == "no-cache"
    assert "data-session-timeout-seconds=\"300\"" in response.content.decode()
    assert "session-timeout-countdown" in response.content.decode()
    assert "session_timeout.js" in response.content.decode()


def test_login_page_is_not_cacheable(client):
    response = client.get(reverse("accounts:login"))

    assert "no-store" in response.headers["Cache-Control"]


@pytest.mark.django_db
def test_logout_prevents_access_to_protected_home(client):
    user_model = get_user_model()
    user = user_model.objects.create_user(username="broker", password="test-pass-123")
    client.force_login(user)

    client.post(reverse("accounts:logout"))
    response = client.get(reverse("core:home"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))


@pytest.mark.django_db
def test_inactive_user_cannot_authenticate(client):
    user_model = get_user_model()
    user_model.objects.create_user(
        username="inactive",
        password="test-pass-123",
        is_active=False,
    )

    response = client.post(
        reverse("accounts:login"),
        {"username": "inactive", "password": "test-pass-123"},
    )

    assert response.status_code == 200
    assert not response.wsgi_request.user.is_authenticated


@pytest.mark.django_db
def test_admin_pages_include_idle_session_warning(client):
    user = get_user_model().objects.create_superuser(
        username="site-admin", email="admin@example.test", password="test-pass-123"
    )
    client.force_login(user)

    response = client.get(reverse("admin:index"))

    assert response.status_code == 200
    assert "session-timeout-warning" in response.content.decode()
    assert "session_timeout.js" in response.content.decode()


@pytest.mark.django_db
def test_approved_roles_are_seeded():
    role_names = set(Group.objects.values_list("name", flat=True))

    assert role_names == {
        "Administrador",
        "Broker",
        "Dispatcher",
        "Gerente administrativo",
        "Gerente general",
    }


@pytest.mark.django_db
def test_administrator_and_managers_have_initial_audit_permissions():
    administrator = Group.objects.get(name="Administrador")
    manager = Group.objects.get(name="Gerente administrativo")
    general_manager = Group.objects.get(name="Gerente general")

    assert administrator.permissions.filter(codename="view_auditevent").exists()
    assert administrator.permissions.filter(codename="view_catalogentry").exists()
    assert administrator.permissions.filter(codename="change_catalogentry").exists()
    assert manager.permissions.filter(codename="view_auditevent").exists()
    assert general_manager.permissions.filter(codename="view_auditevent").exists()


@pytest.mark.django_db
def test_commercial_adjustment_permissions_follow_dispatcher_and_admin_manager_roles():
    dispatcher = Group.objects.get(name="Dispatcher")
    administrative_manager = Group.objects.get(name="Gerente administrativo")
    general_manager = Group.objects.get(name="Gerente general")

    assert dispatcher.permissions.filter(codename="add_commercialadjustment").exists()
    assert dispatcher.permissions.filter(codename="view_commercialadjustment").exists()
    assert not dispatcher.permissions.filter(codename="change_commercialadjustment").exists()
    assert administrative_manager.permissions.filter(
        codename="change_commercialadjustment"
    ).exists()
    assert general_manager.permissions.filter(codename="view_commercialadjustment").exists()


def test_password_reset_page_is_available(client):
    response = client.get(reverse("accounts:password_reset"))

    assert response.status_code == 200
    assert "Restablecer contraseña" in response.content.decode()


@pytest.mark.django_db
def test_successful_password_change_is_audited_without_password_data(client):
    user = get_user_model().objects.create_user(
        username="password-audit-user", password="test-pass-123"
    )
    client.force_login(user)

    response = client.post(
        reverse("accounts:password_change"),
        {
            "old_password": "test-pass-123",
            "new_password1": "new-pass-456-secure",
            "new_password2": "new-pass-456-secure",
        },
    )

    event = AuditEvent.objects.get(action="change_password", entity_id=str(user.pk))
    assert response.status_code == 302
    assert event.actor == user
    assert event.metadata == {}


@pytest.mark.django_db
def test_successful_password_reset_is_audited_without_reset_token(client):
    user = get_user_model().objects.create_user(
        username="password-reset-audit", email="reset@example.test", password="old-pass-123"
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = client.get(
        reverse("accounts:password_reset_confirm", args=(uid, token))
    )
    assert response.status_code == 302
    response = client.get(response.url)
    response = client.post(
        response.request["PATH_INFO"],
        {"new_password1": "new-pass-456-secure", "new_password2": "new-pass-456-secure"},
    )

    event = AuditEvent.objects.get(action="reset_password", entity_id=str(user.pk))
    assert response.status_code == 302
    assert event.actor is None
    assert event.metadata == {}


@pytest.mark.django_db
def test_admin_password_change_is_audited_without_password_data(client):
    administrator = get_user_model().objects.create_superuser(
        username="password-admin", email="password-admin@example.test", password="admin-pass-123"
    )
    target_user = get_user_model().objects.create_user(
        username="password-admin-target", password="old-pass-123"
    )
    client.force_login(administrator)
    password_url = reverse("admin:auth_user_password_change", args=[target_user.pk])

    page = client.get(password_url)
    response = client.post(
        password_url,
        {"password1": "new-admin-pass-456", "password2": "new-admin-pass-456"},
    )

    event = AuditEvent.objects.get(
        actor=administrator,
        action="admin_change_user_password",
        entity_id=str(target_user.pk),
    )
    assert page.status_code == 200
    assert response.status_code == 302
    assert event.metadata == {}


@pytest.mark.django_db
def test_individual_permission_assignment_can_be_reassigned():
    from .permissions import UserPermissionAssignment

    user_model = get_user_model()
    user = user_model.objects.create_user(username="permission-user", password="test-pass-123")
    view_order = Permission.objects.get(codename="view_order")
    view_customer = Permission.objects.get(codename="view_customer")
    assignment = UserPermissionAssignment.objects.create(user=user)
    assignment.permissions.add(view_order)
    assignment.sync_user_permissions()

    assert user.has_perm("orders.view_order")

    assignment.permissions.set([view_customer])
    assignment.sync_user_permissions()
    assert not user.has_perm("orders.view_order")
    assert user.has_perm("customers.view_customer")


@pytest.mark.django_db
def test_admin_user_group_and_individual_permission_changes_are_audited(db):
    from types import SimpleNamespace

    from django.contrib import admin
    from django.test import RequestFactory

    from apps.accounts.admin import (
        AuditedGroupAdmin,
        AuditedUserAdmin,
        UserPermissionAssignmentAdmin,
    )
    from apps.accounts.permissions import UserPermissionAssignment

    user_model = get_user_model()
    administrator = user_model.objects.create_superuser(
        username="audit-admin", email="audit-admin@example.test", password="pass-123456"
    )
    target_user = user_model.objects.create_user(
        username="audit-target", password="pass-123456"
    )
    target_group = Group.objects.get(name="Broker")
    view_order = Permission.objects.get(
        content_type__app_label="orders", codename="view_order"
    )
    request = RequestFactory().post("/admin/")
    request.user = administrator

    target_user.first_name = "Actualizado"
    AuditedUserAdmin(user_model, admin.site).save_model(
        request,
        target_user,
        SimpleNamespace(changed_data=["first_name"]),
        change=True,
    )
    AuditedUserAdmin(user_model, admin.site).save_related(
        request,
        SimpleNamespace(
            instance=target_user,
            save_m2m=lambda: target_user.groups.add(target_group),
        ),
        [],
        change=True,
    )
    assignment = UserPermissionAssignment.objects.create(user=target_user)
    UserPermissionAssignmentAdmin(UserPermissionAssignment, admin.site).save_related(
        request,
        SimpleNamespace(
            instance=assignment,
            save_m2m=lambda: assignment.permissions.add(view_order),
        ),
        [],
        change=False,
    )

    assert AuditEvent.objects.filter(
        actor=administrator, action="update_user", entity_id=str(target_user.pk)
    ).exists()
    assert AuditEvent.objects.filter(
        actor=administrator, action="assign_user_groups", entity_id=str(target_user.pk)
    ).exists()
    permission_event = AuditEvent.objects.get(
        actor=administrator,
        action="assign_user_permissions",
        entity_id=str(target_user.pk),
    )
    assert permission_event.metadata["permissions_after"] == [["orders", "view_order"]]
    assert not AuditedUserAdmin(user_model, admin.site).has_delete_permission(
        request, target_user
    )

    target_group.permissions.clear()
    AuditedGroupAdmin(Group, admin.site).save_related(
        request,
        SimpleNamespace(
            instance=target_group,
            save_m2m=lambda: target_group.permissions.add(view_order),
        ),
        [],
        change=True,
    )
    assert AuditEvent.objects.filter(
        actor=administrator,
        action="update_group_permissions",
        entity_id=str(target_group.pk),
    ).exists()


@pytest.mark.django_db
def test_staff_administrator_can_manage_individual_permission_assignments(client):
    from apps.accounts.permissions import UserPermissionAssignment

    user_model = get_user_model()
    administrator = user_model.objects.create_user(
        username="staff-admin", password="test-pass-123", is_staff=True
    )
    administrator.groups.add(Group.objects.get(name="Administrador"))
    admin_permissions = set(
        Group.objects.get(name="Administrador")
        .permissions.filter(content_type__app_label="accounts")
        .values_list("codename", flat=True)
    )
    assert admin_permissions == {
        "add_userpermissionassignment",
        "change_userpermissionassignment",
        "view_userpermissionassignment",
    }
    assert not administrator.is_superuser
    broker = user_model.objects.create_user(
        username="permission-broker", password="test-pass-123"
    )
    broker.groups.add(Group.objects.get(name="Broker"))
    audit_permission = Permission.objects.get(
        content_type__app_label="audit", codename="view_auditevent"
    )
    assignment_url = reverse("admin:accounts_userpermissionassignment_add")
    client.force_login(administrator)

    assert client.get(assignment_url).status_code == 200
    response = client.post(
        assignment_url,
        {
            "user": broker.pk,
            "permissions": [audit_permission.pk],
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    assignment = UserPermissionAssignment.objects.get(user=broker)
    assert list(assignment.permissions.values_list("pk", flat=True)) == [
        audit_permission.pk
    ]
    assert broker.has_perm("audit.view_auditevent")
    assert AuditEvent.objects.filter(
        actor=administrator,
        action="assign_user_permissions",
        entity_id=str(broker.pk),
    ).exists()

@pytest.mark.django_db
def test_idle_timeout_defaults_to_five_minutes():
    configuration = SystemConfiguration.objects.get(key="session-idle-timeout-minutes")

    assert configuration.value == "5"
    assert idle_timeout_seconds() == 300


@pytest.mark.django_db
def test_idle_timeout_uses_valid_admin_configuration():
    configuration = SystemConfiguration.objects.get(key="session-idle-timeout-minutes")
    configuration.value = "12"
    configuration.full_clean()
    configuration.save()

    assert idle_timeout_seconds() == 720


@pytest.mark.django_db
@pytest.mark.parametrize("value", ("0", "1441", "invalido"))
def test_idle_timeout_configuration_rejects_invalid_values(value):
    configuration = SystemConfiguration.objects.get(key="session-idle-timeout-minutes")
    configuration.value = value

    with pytest.raises(ValidationError):
        configuration.full_clean()


@pytest.mark.django_db
def test_idle_timeout_expires_session_and_records_audit(client):
    user = get_user_model().objects.create_user(username="idle-user", password="test-pass-123")
    client.force_login(user)
    session = client.session
    session[LAST_ACTIVITY_SESSION_KEY] = time.time() - idle_timeout_seconds() - 1
    session.save()

    response = client.get(reverse("core:home"))

    assert response.status_code == 302
    assert response.url.startswith(reverse("accounts:login"))
    event = AuditEvent.objects.get(action="session_idle_timeout")
    assert event.actor == user
    assert event.entity_type == "authentication"
    assert event.metadata == {"timeout_seconds": 300}


@pytest.mark.django_db
def test_user_activity_renews_session_and_returns_deadline(client):
    user = get_user_model().objects.create_user(username="active-user", password="test-pass-123")
    client.force_login(user)
    session = client.session
    old_activity = time.time() - 60
    session[LAST_ACTIVITY_SESSION_KEY] = old_activity
    session.save()

    response = client.post(reverse("accounts:activity"), data="{}", content_type="application/json")

    assert response.status_code == 200
    assert response.json()["authenticated"] is True
    assert response.json()["timeout_seconds"] == 300
    assert response.json()["deadline_ms"] > int((old_activity + 300) * 1000)
    assert client.session[LAST_ACTIVITY_SESSION_KEY] > old_activity


@pytest.mark.django_db
def test_unauthenticated_user_cannot_renew_session(client):
    response = client.post(reverse("accounts:activity"), data="{}", content_type="application/json")

    assert response.status_code == 401


@pytest.mark.django_db
def test_activity_endpoint_accepts_only_post(client):
    user = get_user_model().objects.create_user(username="activity-user", password="test-pass-123")
    client.force_login(user)

    assert client.get(reverse("accounts:activity")).status_code == 405


@pytest.mark.django_db
def test_automated_request_does_not_extend_session(client):
    user = get_user_model().objects.create_user(username="automated-user", password="test-pass-123")
    client.force_login(user)
    session = client.session
    last_activity = time.time() - 60
    session[LAST_ACTIVITY_SESSION_KEY] = last_activity
    session.save()

    response = client.get(reverse("core:home"), HTTP_X_CARGOTRACK_AUTOMATED="true")

    assert response.status_code == 200
    assert client.session[LAST_ACTIVITY_SESSION_KEY] == last_activity


@pytest.mark.django_db
def test_static_asset_request_does_not_extend_idle_session(client):
    user = get_user_model().objects.create_user(username="static-user", password="test-pass-123")
    client.force_login(user)
    session = client.session
    last_activity = time.time() - 30
    session[LAST_ACTIVITY_SESSION_KEY] = last_activity
    session.save()

    client.get("/static/js/app.js")

    assert client.session[LAST_ACTIVITY_SESSION_KEY] == last_activity

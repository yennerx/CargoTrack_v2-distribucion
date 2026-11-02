from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import GroupAdmin as DjangoGroupAdmin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from django.contrib.auth.models import Group, Permission

from apps.audit.models import AuditEvent

from .permissions import UserPermissionAssignment

User = get_user_model()


def permission_codes(permission_ids):
    return list(
        Permission.objects.filter(pk__in=permission_ids)
        .order_by("content_type__app_label", "codename")
        .values_list("content_type__app_label", "codename")
    )


class AuditedUserAdmin(DjangoUserAdmin):
    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        changed_fields = sorted(
            field
            for field in form.changed_data
            if field not in {"password", "last_login"}
        )
        AuditEvent.objects.create(
            actor=request.user,
            action="update_user" if change else "create_user",
            entity_type="user",
            entity_id=str(obj.pk),
            metadata={"changed_fields": changed_fields},
        )

    def save_related(self, request, form, formsets, change):
        user = form.instance
        previous_group_ids = set(user.groups.values_list("pk", flat=True))
        previous_permission_ids = set(user.user_permissions.values_list("pk", flat=True))
        super().save_related(request, form, formsets, change)
        current_group_ids = set(user.groups.values_list("pk", flat=True))
        current_permission_ids = set(user.user_permissions.values_list("pk", flat=True))
        if previous_group_ids != current_group_ids:
            AuditEvent.objects.create(
                actor=request.user,
                action="assign_user_groups",
                entity_type="user",
                entity_id=str(user.pk),
                metadata={
                    "group_ids_before": sorted(previous_group_ids),
                    "group_ids_after": sorted(current_group_ids),
                },
            )
        if previous_permission_ids != current_permission_ids:
            AuditEvent.objects.create(
                actor=request.user,
                action="assign_user_permissions",
                entity_type="user",
                entity_id=str(user.pk),
                metadata={
                    "permissions_before": permission_codes(previous_permission_ids),
                    "permissions_after": permission_codes(current_permission_ids),
                },
            )

    def user_change_password(self, request, id, form_url=""):
        response = super().user_change_password(request, id, form_url)
        if request.method == "POST" and response.status_code in (302, 303):
            target_user = self.get_object(request, id)
            if target_user:
                AuditEvent.objects.create(
                    actor=request.user,
                    action="admin_change_user_password",
                    entity_type="user",
                    entity_id=str(target_user.pk),
                    metadata={},
                )
        return response


class AuditedGroupAdmin(DjangoGroupAdmin):
    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_group" if change else "create_group",
            entity_type="group",
            entity_id=str(obj.pk),
            metadata={
                "group_name": obj.name,
                "changed_fields": sorted(form.changed_data),
            },
        )

    def save_related(self, request, form, formsets, change):
        group = form.instance
        previous_permission_ids = set(group.permissions.values_list("pk", flat=True))
        super().save_related(request, form, formsets, change)
        current_permission_ids = set(group.permissions.values_list("pk", flat=True))
        if previous_permission_ids != current_permission_ids:
            AuditEvent.objects.create(
                actor=request.user,
                action="update_group_permissions",
                entity_type="group",
                entity_id=str(group.pk),
                metadata={
                    "group_name": group.name,
                    "permissions_before": permission_codes(previous_permission_ids),
                    "permissions_after": permission_codes(current_permission_ids),
                },
            )

    def delete_model(self, request, obj):
        AuditEvent.objects.create(
            actor=request.user,
            action="delete_group",
            entity_type="group",
            entity_id=str(obj.pk),
            metadata={"group_name": obj.name},
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        groups = list(queryset.values_list("pk", "name"))
        for group_id, group_name in groups:
            AuditEvent.objects.create(
                actor=request.user,
                action="delete_group",
                entity_type="group",
                entity_id=str(group_id),
                metadata={"group_name": group_name},
            )
        super().delete_queryset(request, queryset)


@admin.register(UserPermissionAssignment)
class UserPermissionAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    filter_horizontal = ("permissions",)
    search_fields = ("user__username", "user__email")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_related(self, request, form, formsets, change):
        user = form.instance.user
        previous_permission_ids = set(user.user_permissions.values_list("pk", flat=True))
        super().save_related(request, form, formsets, change)
        form.instance.sync_user_permissions()
        current_permission_ids = set(user.user_permissions.values_list("pk", flat=True))
        if previous_permission_ids != current_permission_ids:
            AuditEvent.objects.create(
                actor=request.user,
                action="assign_user_permissions",
                entity_type="user",
                entity_id=str(user.pk),
                metadata={
                    "permissions_before": permission_codes(previous_permission_ids),
                    "permissions_after": permission_codes(current_permission_ids),
                },
            )


if admin.site.is_registered(User):
    admin.site.unregister(User)
admin.site.register(User, AuditedUserAdmin)

if admin.site.is_registered(Group):
    admin.site.unregister(Group)
admin.site.register(Group, AuditedGroupAdmin)

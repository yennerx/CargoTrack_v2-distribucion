from django.contrib import admin

from apps.audit.models import AuditEvent

from .models import CatalogEntry, SystemConfiguration


@admin.register(CatalogEntry)
class CatalogEntryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "catalog_type",
        "code",
        "sort_order",
        "is_active",
        "is_system_defined",
    )
    list_filter = ("catalog_type", "is_active", "is_system_defined")
    search_fields = ("name", "code", "description")
    ordering = ("catalog_type", "sort_order", "name")
    readonly_fields = ("is_system_defined", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return bool(obj and not obj.is_system_defined)

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_catalog" if change else "create_catalog",
            entity_type="catalog_entry",
            entity_id=str(obj.pk),
            metadata={"catalog_type": obj.catalog_type, "code": obj.code},
        )

    def delete_model(self, request, obj):
        AuditEvent.objects.create(
            actor=request.user,
            action="delete_catalog",
            entity_type="catalog_entry",
            entity_id=str(obj.pk),
            metadata={"catalog_type": obj.catalog_type, "code": obj.code},
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        entries = list(queryset.values("pk", "catalog_type", "code"))
        for entry in entries:
            AuditEvent.objects.create(
                actor=request.user,
                action="delete_catalog",
                entity_type="catalog_entry",
                entity_id=str(entry["pk"]),
                metadata={
                    "catalog_type": entry["catalog_type"],
                    "code": entry["code"],
                },
            )
        super().delete_queryset(request, queryset)


@admin.register(SystemConfiguration)
class SystemConfigurationAdmin(admin.ModelAdmin):
    list_display = ("key", "value", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("key", "value", "description")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_configuration" if change else "create_configuration",
            entity_type="system_configuration",
            entity_id=str(obj.pk),
            metadata={"key": obj.key},
        )

from django.contrib import admin

from .models import AuditEvent


class ReadOnlyAuditAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AuditEvent)
class AuditEventAdmin(ReadOnlyAuditAdmin):
    list_display = ("created_at", "actor", "action", "entity_type", "entity_id", "order")
    list_filter = ("action", "entity_type", "created_at")
    search_fields = ("entity_type", "entity_id", "actor__username", "order__number")
    readonly_fields = (
        "actor",
        "action",
        "entity_type",
        "entity_id",
        "metadata",
        "ip_address",
        "user_agent",
        "created_at",
        "order",
    )

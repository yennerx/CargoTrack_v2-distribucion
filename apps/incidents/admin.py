from django.contrib import admin

from apps.audit.models import AuditEvent

from .models import Incident, IncidentHistory


@admin.register(Incident)
class IncidentAdmin(admin.ModelAdmin):
    list_display = ("title", "order", "incident_type", "priority", "status", "assigned_to")
    list_filter = ("status", "priority", "incident_type")
    search_fields = ("title", "description", "order__number")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            order=obj.order,
            action="update_incident" if change else "create_incident",
            entity_type="incident",
            entity_id=str(obj.pk),
            metadata={"changed_fields": sorted(form.changed_data)},
        )


@admin.register(IncidentHistory)
class IncidentHistoryAdmin(admin.ModelAdmin):
    list_display = ("incident", "previous_status", "status", "changed_by", "changed_at")
    list_filter = ("status",)
    readonly_fields = (
        "incident",
        "previous_status",
        "status",
        "observation",
        "changed_by",
        "changed_at",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

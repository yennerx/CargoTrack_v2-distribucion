from django.contrib import admin

from apps.audit.admin import ReadOnlyAuditAdmin
from apps.audit.models import AuditEvent
from apps.core.access_scope import active_brokers

from .models import Order, OrderClosureStatus, OrderNumberSequence


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = (
        "number",
        "customer",
        "status",
        "closure_status",
        "proposed_carrier",
        "confirmed_carrier",
        "created_at",
    )
    list_filter = ("status", "closure_status", "cargo_type", "equipment_type")
    search_fields = ("number", "customer__legal_name", "customer__nit")
    readonly_fields = (
        "number",
        "status",
        "closure_status",
        "created_by",
        "created_at",
        "updated_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        if obj and obj.closure_status == OrderClosureStatus.CLOSED:
            return False
        return super().has_change_permission(request, obj)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "broker":
            kwargs["queryset"] = active_brokers()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        previous_broker_id = obj.broker_id if change else None
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            order=obj,
            action="update_order" if change else "create_order",
            entity_type="order",
            entity_id=str(obj.pk),
            metadata={
                "number": obj.number,
                "broker_id_before": previous_broker_id,
                "broker_id_after": obj.broker_id,
                "created_by_id": obj.created_by_id,
            },
        )


@admin.register(OrderNumberSequence)
class OrderNumberSequenceAdmin(ReadOnlyAuditAdmin):
    list_display = ("year", "last_number")

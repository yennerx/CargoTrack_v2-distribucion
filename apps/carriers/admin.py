from django.contrib import admin

from apps.audit.models import AuditEvent
from apps.core.access_scope import active_brokers

from .models import Carrier, CarrierDocument, CarrierUnit


class CarrierUnitInline(admin.TabularInline):
    model = CarrierUnit
    extra = 0


class CarrierDocumentInline(admin.TabularInline):
    model = CarrierDocument
    extra = 0


@admin.register(Carrier)
class CarrierAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "nit", "carrier_type", "is_validated", "is_active", "updated_at")
    list_filter = ("carrier_type", "is_validated", "is_active")
    search_fields = ("legal_name", "commercial_name", "nit")
    readonly_fields = ("created_by", "created_at", "updated_at", "validated_by", "validated_at")
    inlines = (CarrierUnitInline, CarrierDocumentInline)

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "brokers":
            field.queryset = active_brokers()
            field.required = True
        return field

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_carrier" if change else "create_carrier",
            entity_type="carrier",
            entity_id=str(obj.pk),
            metadata={},
        )

    def save_related(self, request, form, formsets, change):
        previous_brokers = list(form.instance.brokers.values_list("pk", flat=True))
        super().save_related(request, form, formsets, change)
        current_brokers = list(form.instance.brokers.values_list("pk", flat=True))
        if previous_brokers != current_brokers:
            AuditEvent.objects.create(
                actor=request.user,
                action="assign_carrier_brokers",
                entity_type="carrier",
                entity_id=str(form.instance.pk),
                metadata={
                    "broker_ids_before": previous_brokers,
                    "broker_ids_after": current_brokers,
                },
            )

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if not formset.has_changed():
            return
        related_name = {
            CarrierUnit: "units",
            CarrierDocument: "documents",
        }[formset.model]
        AuditEvent.objects.create(
            actor=request.user,
            action=f"update_carrier_{related_name}",
            entity_type="carrier",
            entity_id=str(form.instance.pk),
            metadata={
                "created_count": len(formset.new_objects),
                "updated_count": len(formset.changed_objects),
                "deleted_count": len(formset.deleted_objects),
            },
        )

@admin.register(CarrierUnit)
class CarrierUnitAdmin(admin.ModelAdmin):
    list_display = ("unit_identifier", "carrier", "license_plate", "equipment_type", "is_active")
    list_filter = ("is_active", "equipment_type")
    search_fields = ("unit_identifier", "license_plate", "carrier__nit", "carrier__legal_name")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_carrier_unit" if change else "create_carrier_unit",
            entity_type="carrier_unit",
            entity_id=str(obj.pk),
            metadata={"carrier_id": obj.carrier_id},
        )


@admin.register(CarrierDocument)
class CarrierDocumentAdmin(admin.ModelAdmin):
    list_display = (
        "document_type",
        "document_number",
        "carrier",
        "expires_at",
        "is_validated",
        "is_active",
    )
    list_filter = ("document_type", "is_validated", "is_active")
    search_fields = ("document_number", "carrier__nit", "carrier__legal_name")
    readonly_fields = ("validated_by", "validated_at", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_carrier_document" if change else "create_carrier_document",
            entity_type="carrier_document",
            entity_id=str(obj.pk),
            metadata={
                "carrier_id": obj.carrier_id,
                "document_type": obj.document_type.code,
            },
        )

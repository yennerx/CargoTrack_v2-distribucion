from django.contrib import admin

from apps.audit.models import AuditEvent
from apps.core.access_scope import active_brokers

from .models import Customer, CustomerContact


class CustomerContactInline(admin.TabularInline):
    model = CustomerContact
    extra = 0


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    list_display = ("legal_name", "nit", "is_active", "updated_at")
    list_filter = ("is_active",)
    search_fields = ("legal_name", "commercial_name", "nit")
    readonly_fields = ("created_by", "created_at", "updated_at")
    inlines = (CustomerContactInline,)

    def has_delete_permission(self, request, obj=None):
        return False

    def formfield_for_manytomany(self, db_field, request, **kwargs):
        field = super().formfield_for_manytomany(db_field, request, **kwargs)
        if db_field.name == "brokers":
            field.queryset = active_brokers()
            field.required = True
        return field

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_customer" if change else "create_customer",
            entity_type="customer",
            entity_id=str(obj.pk),
            metadata={},
        )

    def save_formset(self, request, form, formset, change):
        super().save_formset(request, form, formset, change)
        if not formset.has_changed():
            return
        AuditEvent.objects.create(
            actor=request.user,
            action="update_customer_contacts",
            entity_type="customer",
            entity_id=str(form.instance.pk),
            metadata={
                "created_count": len(formset.new_objects),
                "updated_count": len(formset.changed_objects),
                "deleted_count": len(formset.deleted_objects),
            },
        )

    def save_related(self, request, form, formsets, change):
        previous_brokers = list(form.instance.brokers.values_list("pk", flat=True))
        super().save_related(request, form, formsets, change)
        current_brokers = list(form.instance.brokers.values_list("pk", flat=True))
        if previous_brokers != current_brokers:
            AuditEvent.objects.create(
                actor=request.user,
                action="assign_customer_brokers",
                entity_type="customer",
                entity_id=str(form.instance.pk),
                metadata={
                    "broker_ids_before": previous_brokers,
                    "broker_ids_after": current_brokers,
                },
            )


@admin.register(CustomerContact)
class CustomerContactAdmin(admin.ModelAdmin):
    list_display = ("name", "customer", "email", "is_primary", "is_active", "updated_at")
    list_filter = ("is_primary", "is_active")
    search_fields = ("name", "email", "customer__legal_name", "customer__nit")
    readonly_fields = ("created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_customer_contact" if change else "create_customer_contact",
            entity_type="customer_contact",
            entity_id=str(obj.pk),
            metadata={"customer_id": obj.customer_id},
        )

from django.contrib import admin

from apps.audit.admin import ReadOnlyAuditAdmin
from apps.audit.models import AuditEvent

from .models import (
    BrokerDebt,
    CommercialAdjustment,
    Commission,
    CommissionDebtApplication,
    CommissionRule,
    FinancialTransaction,
)


@admin.register(FinancialTransaction)
class FinancialTransactionAdmin(ReadOnlyAuditAdmin):
    list_display = ("order", "movement_type", "amount", "currency", "status", "transaction_date")
    list_filter = ("status", "movement_type", "currency")
    search_fields = ("order__number", "reference", "description")
    readonly_fields = (
        "base_amount_usd",
        "created_by",
        "confirmed_by",
        "confirmed_at",
        "created_at",
        "updated_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommissionRule)
class CommissionRuleAdmin(admin.ModelAdmin):
    list_display = ("broker", "percentage", "valid_from", "valid_to", "is_active")
    list_filter = ("is_active",)
    search_fields = ("broker__username", "broker__first_name", "broker__last_name")
    readonly_fields = ("created_by", "created_at", "updated_at")

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        if not obj.created_by_id:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
        AuditEvent.objects.create(
            actor=request.user,
            action="update_commission_rule" if change else "create_commission_rule",
            entity_type="commission_rule",
            entity_id=str(obj.pk),
            metadata={"broker_id": obj.broker_id},
        )

@admin.register(Commission)
class CommissionAdmin(ReadOnlyAuditAdmin):
    list_display = ("order", "broker", "commission_amount_usd", "status", "paid_at")
    list_filter = ("status",)
    search_fields = ("order__number", "broker__username")
    readonly_fields = (
        "broker", "rule", "gross_profit_usd", "commission_rate", "gross_commission_usd",
        "customer_unpaid_discount_usd", "commission_amount_usd", "loss_amount_usd",
        "company_covered_loss_usd", "agreed_broker_debt_usd", "calculated_by", "calculated_at",
        "authorized_by", "authorized_at", "paid_by", "paid_at", "created_at", "updated_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(BrokerDebt)
class BrokerDebtAdmin(ReadOnlyAuditAdmin):
    list_display = ("broker", "agreed_amount_usd", "balance_usd", "status", "approved_at")
    list_filter = ("status",)
    search_fields = ("broker__username", "origin_commission__order__number")
    readonly_fields = (
        "broker", "origin_commission", "loss_amount_usd", "company_covered_loss_usd",
        "agreed_amount_usd", "balance_usd", "approved_by", "approved_at",
        "created_at", "updated_at",
    )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommissionDebtApplication)
class CommissionDebtApplicationAdmin(ReadOnlyAuditAdmin):
    list_display = ("debt", "commission", "amount_usd", "applied_by", "applied_at")
    readonly_fields = ("debt", "commission", "amount_usd", "applied_by", "applied_at")

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CommercialAdjustment)
class CommercialAdjustmentAdmin(ReadOnlyAuditAdmin):
    list_display = (
        "order",
        "target",
        "amount_usd",
        "status",
        "requested_by",
        "requested_at",
        "reviewed_by",
        "reviewed_at",
    )
    list_filter = ("status", "target")
    search_fields = ("order__number", "reason", "reference")
    readonly_fields = tuple(field.name for field in CommercialAdjustment._meta.fields)

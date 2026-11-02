from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

SENSITIVE_METADATA_KEYS = {
    "amount",
    "amount_usd",
    "access_token",
    "address",
    "balance_usd",
    "broker",
    "broker_debt_usd",
    "carrier_cost",
    "carrier",
    "commission_amount_usd",
    "commission_rate",
    "company_covered_usd",
    "customer",
    "customer_rate",
    "description",
    "document_number",
    "email",
    "first_name",
    "gross_commission_usd",
    "gross_profit_usd",
    "loss_amount_usd",
    "nit",
    "last_name",
    "order_id",
    "original_name",
    "password",
    "payment_method",
    "payment_reference",
    "phone",
    "reference",
    "percentage",
    "secret",
    "stored_name",
    "token",
    "user_agent",
    "observation",
}


def sensitive_metadata_keys(value, *, prefix=""):
    if isinstance(value, dict):
        keys = set()
        for key, nested_value in value.items():
            normalized_key = str(key).strip().lower()
            if normalized_key in SENSITIVE_METADATA_KEYS:
                keys.add(f"{prefix}{normalized_key}")
            keys.update(
                sensitive_metadata_keys(nested_value, prefix=f"{prefix}{key}.")
            )
        return keys
    if isinstance(value, list | tuple):
        return set().union(
            *(sensitive_metadata_keys(item, prefix=prefix) for item in value), set()
        )
    return set()


class ImmutableAuditQuerySet(models.QuerySet):
    def bulk_create(self, objs, **kwargs):
        if kwargs.get("update_conflicts"):
            raise ValidationError("Los eventos de auditoría no se pueden actualizar.")
        objs = list(objs)
        for obj in objs:
            if not obj._state.adding or obj.pk is not None:
                raise ValidationError("Solo se pueden agregar eventos nuevos.")
            obj.full_clean()
        return super().bulk_create(objs, **kwargs)

    def update(self, **kwargs):
        raise ValidationError("Los eventos de auditoría son inmutables.")

    def delete(self):
        raise ValidationError("Los eventos de auditoría son inmutables.")

    def update_or_create(self, defaults=None, create_defaults=None, **kwargs):
        if self.filter(**kwargs).exists():
            raise ValidationError("Los eventos de auditoría no se pueden actualizar.")
        return super().update_or_create(
            defaults=defaults, create_defaults=create_defaults, **kwargs
        )


class AuditEvent(models.Model):
    objects = ImmutableAuditQuerySet.as_manager()

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    order = models.ForeignKey(
        "orders.Order",
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="audit_events",
    )
    action = models.CharField(max_length=50)
    entity_type = models.CharField(max_length=100)
    entity_id = models.CharField(max_length=100, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    user_agent = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("order", "created_at"), name="audit_order_created_idx"
            )
        ]

    def clean(self):
        if not isinstance(self.metadata, dict):
            raise ValidationError({"metadata": "Los metadatos deben ser un objeto."})
        sensitive_keys = sensitive_metadata_keys(self.metadata)
        if sensitive_keys:
            raise ValidationError(
                {
                    "metadata": (
                        "No se permite registrar valores sensibles: "
                        + ", ".join(sorted(sensitive_keys))
                    )
                }
            )

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Los eventos de auditoría son inmutables.")
        self.full_clean()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Los eventos de auditoría son inmutables.")

    def __str__(self):
        return f"{self.action} - {self.entity_type}"

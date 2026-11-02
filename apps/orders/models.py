from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.carriers.models import Carrier
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer

CLOSURE_CATALOG_CODES = {"pendiente-cierre", "cerrada", "reabierta"}


class OrderClosureStatus(models.TextChoices):
    OPEN = "open", "Abierta"
    PENDING = "pending", "Pendiente de cierre"
    CLOSED = "closed", "Cerrada"
    REOPENED = "reopened", "Reabierta"


class OrderNumberSequence(models.Model):
    year = models.PositiveIntegerField(unique=True)
    last_number = models.PositiveIntegerField(default=0)


class Order(models.Model):
    number = models.CharField(max_length=20, unique=True, blank=True)
    status = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="orders",
        limit_choices_to={"catalog_type": CatalogType.ORDER_STATUS},
    )
    closure_status = models.CharField(
        max_length=20,
        choices=OrderClosureStatus.choices,
        default=OrderClosureStatus.OPEN,
    )
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    proposed_carrier = models.ForeignKey(
        Carrier,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="proposed_orders",
    )
    confirmed_carrier = models.ForeignKey(
        Carrier,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="confirmed_orders",
    )
    broker = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="broker_orders",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_orders",
    )
    dispatcher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="dispatcher_orders",
    )
    cargo_type = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="cargo_orders",
        limit_choices_to={"catalog_type": CatalogType.CARGO_TYPE},
    )
    equipment_type = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="equipment_orders",
        limit_choices_to={"catalog_type": CatalogType.EQUIPMENT_TYPE},
    )
    origin = models.CharField(max_length=255)
    destination = models.CharField(max_length=255)
    pickup_date = models.DateField()
    delivery_date = models.DateField()
    customer_rate = models.DecimalField(max_digits=12, decimal_places=2)
    carrier_cost = models.DecimalField(max_digits=12, decimal_places=2)
    rate_conditions = models.TextField(blank=True)
    logistics_notes = models.TextField(blank=True)
    proposed_at = models.DateTimeField(blank=True, null=True)
    confirmed_at = models.DateTimeField(blank=True, null=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="confirmed_orders",
    )
    formalized_at = models.DateTimeField(blank=True, null=True)
    formalized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="formalized_orders",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("customer", "created_at")),
        ]

    def clean(self):
        errors = {}
        if self.status_id and self.status.catalog_type != CatalogType.ORDER_STATUS:
            errors["status"] = "Seleccione un estado operativo válido."
        elif self.status_id and self.status.code in CLOSURE_CATALOG_CODES:
            errors["status"] = "El estado de cierre se registra por separado."
        if self.cargo_type_id and self.cargo_type.catalog_type != CatalogType.CARGO_TYPE:
            errors["cargo_type"] = "Seleccione un tipo de carga válido."
        if (
            self.equipment_type_id
            and self.equipment_type.catalog_type != CatalogType.EQUIPMENT_TYPE
        ):
            errors["equipment_type"] = "Seleccione un tipo de equipo válido."
        if self.pickup_date and self.delivery_date and self.delivery_date < self.pickup_date:
            errors["delivery_date"] = "La entrega no puede ser anterior a la recogida."
        if self.customer_rate is not None and self.customer_rate < Decimal("0"):
            errors["customer_rate"] = "La tarifa al cliente no puede ser negativa."
        if self.carrier_cost is not None and self.carrier_cost < Decimal("0"):
            errors["carrier_cost"] = "El costo del transportista no puede ser negativo."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.number


class OrderStatusHistory(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="status_history")
    previous_status = models.ForeignKey(
        CatalogEntry,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="previous_order_status_history",
    )
    status = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="order_status_history",
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="order_status_changes",
    )
    observation = models.TextField(blank=True)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at",)

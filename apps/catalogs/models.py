from django.core.exceptions import ValidationError
from django.db import models


class CatalogType(models.TextChoices):
    ORDER_STATUS = "order_status", "Estados de orden"
    DOCUMENT_TYPE = "document_type", "Tipo documental"
    CARGO_TYPE = "cargo_type", "Tipo de carga"
    EQUIPMENT_TYPE = "equipment_type", "Tipo de equipo"
    INCIDENT_TYPE = "incident_type", "Tipo de incidencia"
    INCIDENT_PRIORITY = "incident_priority", "Prioridad de incidencia"
    FINANCIAL_MOVEMENT = "financial_movement", "Movimiento financiero"
    EXPENSE_TYPE = "expense_type", "Tipo de gasto"
    CURRENCY = "currency", "Moneda"
    COST_TYPE = "cost_type", "Tipo de costo"


class CatalogEntry(models.Model):
    catalog_type = models.CharField(max_length=40, choices=CatalogType.choices)
    code = models.SlugField(max_length=60)
    name = models.CharField(max_length=120)
    description = models.CharField(max_length=255, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    is_system_defined = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("catalog_type", "sort_order", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("catalog_type", "code"),
                name="unique_catalog_type_code",
            ),
        ]
        indexes = [
            models.Index(fields=("catalog_type", "is_active")),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_catalog_type_display()})"


class SystemConfiguration(models.Model):
    key = models.SlugField(max_length=80, unique=True)
    value = models.CharField(max_length=255)
    description = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("key",)

    def clean(self):
        if self.key != "session-idle-timeout-minutes":
            return
        try:
            timeout_minutes = int(self.value)
        except (TypeError, ValueError) as error:
            raise ValidationError({"value": "Ingrese una cantidad entera de minutos."}) from error
        if not 1 <= timeout_minutes <= 1440:
            raise ValidationError({"value": "El tiempo debe estar entre 1 y 1440 minutos."})

    def __str__(self):
        return self.key

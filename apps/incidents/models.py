from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.catalogs.models import CatalogEntry, CatalogType
from apps.orders.models import Order


class IncidentStatus(models.TextChoices):
    OPEN = "open", "Abierta"
    IN_PROGRESS = "in_progress", "En seguimiento"
    RESOLVED = "resolved", "Resuelta"
    CLOSED = "closed", "Cerrada"
    REOPENED = "reopened", "Reabierta"


class Incident(models.Model):
    order = models.ForeignKey(Order, on_delete=models.PROTECT, related_name="incidents")
    incident_type = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="incidents",
        limit_choices_to={"catalog_type": CatalogType.INCIDENT_TYPE},
    )
    priority = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="priority_incidents",
        limit_choices_to={"catalog_type": CatalogType.INCIDENT_PRIORITY},
    )
    status = models.CharField(
        max_length=20,
        choices=IncidentStatus.choices,
        default=IncidentStatus.OPEN,
    )
    title = models.CharField(max_length=200)
    description = models.TextField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="assigned_incidents",
    )
    resolution = models.TextField(blank=True)
    resolved_at = models.DateTimeField(blank=True, null=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="resolved_incidents",
    )
    closed_at = models.DateTimeField(blank=True, null=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="closed_incidents",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_incidents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = [
            models.Index(
                fields=("order", "status"), name="incidents_i_order_i_5b7e9f_idx"
            ),
            models.Index(
                fields=("priority", "status"), name="incidents_i_priorit_2ecaa6_idx"
            ),
        ]

    def clean(self):
        errors = {}
        if self.incident_type_id and self.incident_type.catalog_type != CatalogType.INCIDENT_TYPE:
            errors["incident_type"] = "Seleccione un tipo de incidencia válido."
        if self.priority_id and self.priority.catalog_type != CatalogType.INCIDENT_PRIORITY:
            errors["priority"] = "Seleccione una prioridad válida."
        if (
            self.status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED)
            and not self.resolution.strip()
        ):
            errors["resolution"] = "La resolución es obligatoria para este estado."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return self.title


class IncidentHistory(models.Model):
    incident = models.ForeignKey(Incident, on_delete=models.PROTECT, related_name="history")
    previous_status = models.CharField(max_length=20, choices=IncidentStatus.choices, blank=True)
    status = models.CharField(max_length=20, choices=IncidentStatus.choices)
    observation = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="incident_history_changes",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-changed_at",)

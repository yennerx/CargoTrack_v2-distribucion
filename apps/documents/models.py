from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.carriers.models import Carrier, CarrierDocument
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.incidents.models import Incident
from apps.orders.models import Order


def document_upload_to(instance, filename):
    if instance.document.order_id:
        target_type = "ordenes"
        target_id = instance.document.order_id
    elif instance.document.carrier_id:
        target_type = "transportistas"
        target_id = instance.document.carrier_id
    else:
        target_type = "incidencias"
        target_id = instance.document.incident_id
    return f"documentos/{target_type}/{target_id}/{instance.stored_name}"


class AttachmentSequence(models.Model):
    last_number = models.PositiveBigIntegerField(default=0)


class Document(models.Model):
    document_type = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="documents",
        limit_choices_to={"catalog_type": CatalogType.DOCUMENT_TYPE},
    )
    order = models.ForeignKey(
        Order,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    carrier = models.ForeignKey(
        Carrier,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    incident = models.ForeignKey(
        Incident,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    carrier_document = models.ForeignKey(
        CarrierDocument,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="attachments",
    )
    stage = models.ForeignKey(
        CatalogEntry,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="stage_documents",
        limit_choices_to={"catalog_type": CatalogType.ORDER_STATUS},
    )
    related_event = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_documents",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-created_at",)
        constraints = [
            models.CheckConstraint(
                condition=(
                    (
                        models.Q(order__isnull=False)
                        & models.Q(carrier__isnull=True)
                        & models.Q(incident__isnull=True)
                    )
                    | (
                        models.Q(order__isnull=True)
                        & models.Q(carrier__isnull=False)
                        & models.Q(incident__isnull=True)
                    )
                    | (
                        models.Q(order__isnull=True)
                        & models.Q(carrier__isnull=True)
                        & models.Q(incident__isnull=False)
                    )
                ),
                name="document_exactly_one_target",
            ),
        ]

    def clean(self):
        errors = {}
        if self.document_type_id and self.document_type.catalog_type != CatalogType.DOCUMENT_TYPE:
            errors["document_type"] = "Seleccione un tipo documental válido."
        if self.stage_id and self.stage.catalog_type != CatalogType.ORDER_STATUS:
            errors["stage"] = "Seleccione una etapa operativa válida."
        if self.carrier_document_id and self.carrier_document.carrier_id != self.carrier_id:
            errors["carrier_document"] = (
                "El documento del transportista no coincide con el expediente."
            )
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        if self.order_id:
            target = self.order.number
        elif self.carrier_id:
            target = self.carrier.legal_name
        else:
            target = self.incident.title
        return f"{self.document_type.name} - {target}"


class DocumentVersion(models.Model):
    document = models.ForeignKey(Document, on_delete=models.PROTECT, related_name="versions")
    version = models.PositiveIntegerField()
    file = models.FileField(upload_to=document_upload_to, validators=[])
    stored_name = models.CharField(max_length=120, unique=True)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100)
    size = models.PositiveBigIntegerField()
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="uploaded_document_versions",
    )
    is_current = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="deleted_document_versions",
    )
    deleted_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("-version",)
        constraints = [
            models.UniqueConstraint(fields=("document", "version"), name="unique_document_version"),
            models.UniqueConstraint(
                fields=("document",),
                condition=models.Q(is_current=True, is_deleted=False),
                name="one_current_document_version",
            ),
        ]

    def clean(self):
        if self.file and not self.is_deleted:
            from .validators import validate_document_file

            validate_document_file(self.file)

    @property
    def extension(self):
        return Path(self.original_name).suffix.lower().lstrip(".")

    def __str__(self):
        return f"{self.document} v{self.version}"

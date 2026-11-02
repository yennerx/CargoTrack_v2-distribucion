import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.catalogs.models import CatalogEntry, CatalogType


class CarrierType(models.TextChoices):
    PERSON = "person", "Persona individual"
    COMPANY = "company", "Empresa"


class Carrier(models.Model):
    carrier_type = models.CharField(max_length=20, choices=CarrierType.choices)
    nit = models.CharField(max_length=30, unique=True, db_index=True)
    legal_name = models.CharField(max_length=200)
    commercial_name = models.CharField(max_length=200, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    primary_phone = models.CharField(max_length=40)
    email = models.EmailField()
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_validated = models.BooleanField(default=False)
    brokers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="assigned_carriers",
    )
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="validated_carriers",
    )
    validated_at = models.DateTimeField(blank=True, null=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_carriers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("legal_name", "nit")
        constraints = [
            models.CheckConstraint(condition=~models.Q(nit=""), name="carrier_nit_not_blank"),
        ]

    def save(self, *args, **kwargs):
        self.nit = re.sub(r"[\s-]+", "", self.nit).upper()
        if not re.fullmatch(r"[A-Z0-9]{3,30}", self.nit):
            raise ValidationError("Ingrese un NIT válido, sin caracteres especiales.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.legal_name} ({self.nit})"


class CarrierUnit(models.Model):
    carrier = models.ForeignKey(Carrier, on_delete=models.PROTECT, related_name="units")
    equipment_type = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="carrier_units",
    )
    unit_identifier = models.CharField(max_length=80)
    license_plate = models.CharField(max_length=30)
    brand = models.CharField(max_length=80, blank=True)
    model = models.CharField(max_length=80, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("unit_identifier",)
        constraints = [
            models.UniqueConstraint(
                fields=("carrier", "unit_identifier"),
                name="unique_carrier_unit_identifier",
            ),
            models.UniqueConstraint(
                fields=("license_plate",),
                condition=models.Q(is_active=True),
                name="unique_active_license_plate",
            ),
        ]

    def clean(self):
        if (
            self.equipment_type_id
            and self.equipment_type.catalog_type != CatalogType.EQUIPMENT_TYPE
        ):
            raise ValidationError({"equipment_type": "Seleccione un tipo de equipo válido."})

    def __str__(self):
        return f"{self.unit_identifier} ({self.license_plate})"


class CarrierDocument(models.Model):
    carrier = models.ForeignKey(Carrier, on_delete=models.PROTECT, related_name="documents")
    document_type = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="carrier_documents",
    )
    document_number = models.CharField(max_length=100)
    issued_at = models.DateField(blank=True, null=True)
    expires_at = models.DateField()
    notes = models.TextField(blank=True)
    is_validated = models.BooleanField(default=False)
    validated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="validated_carrier_documents",
    )
    validated_at = models.DateTimeField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("expires_at", "document_type")

    def clean(self):
        if self.document_type_id and self.document_type.catalog_type != CatalogType.DOCUMENT_TYPE:
            raise ValidationError({"document_type": "Seleccione un tipo documental válido."})
        if self.issued_at and self.expires_at < self.issued_at:
            raise ValidationError(
                {"expires_at": "El vencimiento no puede ser anterior a la emisión."}
            )

    def __str__(self):
        return f"{self.document_type.name} - {self.document_number}"

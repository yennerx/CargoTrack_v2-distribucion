import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models


class Customer(models.Model):
    nit = models.CharField(max_length=30, unique=True, db_index=True)
    legal_name = models.CharField(max_length=200)
    commercial_name = models.CharField(max_length=200, blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    brokers = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="assigned_customers",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_customers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("legal_name", "nit")
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(nit=""),
                name="customer_nit_not_blank",
            ),
        ]
        indexes = [
            models.Index(fields=("is_active", "legal_name")),
        ]

    def save(self, *args, **kwargs):
        self.nit = re.sub(r"[\s-]+", "", self.nit).upper()
        if not re.fullmatch(r"[A-Z0-9]{3,30}", self.nit):
            raise ValidationError("Ingrese un NIT válido, sin caracteres especiales.")
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.legal_name} ({self.nit})"


class CustomerContact(models.Model):
    customer = models.ForeignKey(
        Customer,
        on_delete=models.PROTECT,
        related_name="contacts",
    )
    name = models.CharField(max_length=150)
    position = models.CharField(max_length=120, blank=True)
    primary_phone = models.CharField(max_length=40)
    secondary_phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField()
    preferred_contact_method = models.CharField(max_length=30, blank=True)
    is_primary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-is_primary", "name")
        constraints = [
            models.UniqueConstraint(
                fields=("customer",),
                condition=models.Q(is_primary=True, is_active=True),
                name="one_active_primary_contact",
            ),
        ]

    def __str__(self):
        return f"{self.name} - {self.customer.legal_name}"

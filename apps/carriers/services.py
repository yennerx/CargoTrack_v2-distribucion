from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from .models import CarrierDocument

REQUIRED_DOCUMENT_CODES = {"licencia", "seguro", "tarjeta-de-circulacion", "permiso"}


@transaction.atomic
def validate_carrier(carrier, user):
    today = timezone.localdate()
    required_documents = carrier.documents.filter(
        is_active=True,
        document_type__code__in=REQUIRED_DOCUMENT_CODES,
        expires_at__gte=today,
    )
    available_codes = set(required_documents.values_list("document_type__code", flat=True))
    missing_codes = REQUIRED_DOCUMENT_CODES - available_codes
    if missing_codes:
        raise ValidationError(
            "Faltan documentos vigentes obligatorios para validar el transportista."
        )

    CarrierDocument.objects.filter(carrier=carrier, is_active=True).update(
        is_validated=True,
        validated_by=user,
        validated_at=timezone.now(),
    )
    carrier.is_validated = True
    carrier.validated_by = user
    carrier.validated_at = timezone.now()
    carrier.save(update_fields=("is_validated", "validated_by", "validated_at", "updated_at"))
    return carrier


def document_is_expiring_soon(document):
    today = timezone.localdate()
    alert_days = settings.CARRIER_EXPIRY_ALERT_DAYS
    return today <= document.expires_at <= today + timedelta(days=alert_days)

from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditEvent

from .models import AttachmentSequence, Document, DocumentVersion
from .validators import validate_document_file


def order_needs_invoice_or_receipt(order):
    return not order_has_document_type(order, "factura", "recibo")


def order_has_document_type(order, *codes):
    return order.documents.filter(is_active=True, document_type__code__in=codes).exists()


def order_closing_document_errors(order):
    errors = []
    if not order_has_document_type(order, "constancia-entrega"):
        errors.append("Falta la constancia de entrega.")
    if order_needs_invoice_or_receipt(order):
        errors.append("Debe existir una factura o recibo.")
    transactions = order.financial_transactions.exclude(status="voided")
    if transactions.filter(status="pending").exists():
        errors.append("Todos los movimientos financieros deben estar confirmados.")
    if transactions.filter(movement_type__code="cobro-cliente").exists() and not (
        order_has_document_type(order, "comprobante-cobro")
    ):
        errors.append("Falta el comprobante de cobro.")
    if transactions.filter(
        movement_type__code__in=("pago-transportista", "gasto-transporte", "otro-gasto")
    ).exists() and not order_has_document_type(order, "comprobante-gasto"):
        errors.append("Falta el comprobante de gasto.")
    return errors


def is_administrator(user):
    return user.is_superuser or user.groups.filter(name="Administrador").exists()


def next_stored_name(uploaded_file):
    extension = Path(uploaded_file.name).suffix.lower().lstrip(".")
    with transaction.atomic():
        sequence, _created = AttachmentSequence.objects.select_for_update().get_or_create(pk=1)
        sequence.last_number += 1
        sequence.save(update_fields=("last_number",))
        return f"ATT-{sequence.last_number:08d}.{extension}"


def upload_document(*, uploaded_file, actor, document_data, target):
    extension, content_type = validate_document_file(uploaded_file)
    with transaction.atomic():
        document = Document.objects.create(
            document_type=document_data["document_type"],
            order=target if document_data["target_type"] == "order" else None,
            carrier=target if document_data["target_type"] == "carrier" else None,
            incident=target if document_data["target_type"] == "incident" else None,
            carrier_document=document_data.get("carrier_document"),
            stage=document_data.get("stage"),
            related_event=document_data.get("related_event", "").strip(),
            created_by=actor,
        )
        version = create_version(
            document=document,
            uploaded_file=uploaded_file,
            actor=actor,
            version_number=1,
            extension=extension,
            content_type=content_type,
        )
        audit_document(actor, "upload_document", document, version)
    return document


def create_version(
    *, document, uploaded_file, actor, version_number, extension=None, content_type=None
):
    if extension is None or content_type is None:
        extension, content_type = validate_document_file(uploaded_file)
    original_name = uploaded_file.name
    DocumentVersion.objects.filter(document=document, is_current=True).update(is_current=False)
    stored_name = next_stored_name(uploaded_file)
    uploaded_file.name = stored_name
    return DocumentVersion.objects.create(
        document=document,
        version=version_number,
        file=uploaded_file,
        stored_name=stored_name,
        original_name=original_name,
        content_type=content_type,
        size=uploaded_file.size,
        uploaded_by=actor,
    )


def upload_version(*, document, uploaded_file, actor):
    if not is_administrator(actor) and not actor.has_perm("documents.add_documentversion"):
        raise ValidationError("No tiene permiso para cargar una versión.")
    current_version = document.versions.filter(is_deleted=False).order_by("-version").first()
    next_version = (current_version.version + 1) if current_version else 1
    with transaction.atomic():
        version = create_version(
            document=document,
            uploaded_file=uploaded_file,
            actor=actor,
            version_number=next_version,
        )
        audit_document(actor, "upload_document_version", document, version)
    return version


def restore_version(*, version, actor):
    if not is_administrator(actor):
        raise ValidationError("Solo el Administrador puede restaurar versiones.")
    if version.is_deleted:
        raise ValidationError("No se puede restaurar una versión eliminada.")
    with transaction.atomic():
        DocumentVersion.objects.filter(document=version.document, is_current=True).update(
            is_current=False
        )
        version.is_current = True
        version.document.is_active = True
        version.document.save(update_fields=("is_active", "updated_at"))
        version.save(update_fields=("is_current",))
        audit_document(actor, "restore_document_version", version.document, version)


def delete_version(*, version, actor):
    if not is_administrator(actor):
        raise ValidationError("Solo el Administrador puede eliminar archivos.")
    with transaction.atomic():
        version.file.delete(save=False)
        version.is_deleted = True
        version.is_current = False
        version.deleted_by = actor
        version.deleted_at = timezone.now()
        version.save(update_fields=("is_deleted", "is_current", "deleted_by", "deleted_at"))
        replacement = (
            version.document.versions.filter(is_deleted=False).order_by("-version").first()
        )
        if replacement:
            replacement.is_current = True
            replacement.save(update_fields=("is_current",))
        else:
            version.document.is_active = False
            version.document.save(update_fields=("is_active", "updated_at"))
        audit_document(actor, "delete_document_version", version.document, version)


def audit_document(actor, action, document, version):
    order = document.order
    if order is None and document.incident_id:
        order = document.incident.order
    AuditEvent.objects.create(
        actor=actor,
        order=order,
        action=action,
        entity_type="document",
        entity_id=str(document.pk),
        metadata={
            "version": version.version,
            "document_type": document.document_type.code,
        },
    )

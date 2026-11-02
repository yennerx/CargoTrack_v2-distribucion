from django.contrib import admin

from apps.audit.admin import ReadOnlyAuditAdmin

from .models import AttachmentSequence, Document, DocumentVersion


@admin.register(Document)
class DocumentAdmin(ReadOnlyAuditAdmin):
    list_display = ("document_type", "order", "carrier", "is_active", "created_at")
    list_filter = ("document_type", "is_active")
    search_fields = ("order__number", "carrier__nit", "carrier__legal_name")
    readonly_fields = ("created_by", "created_at", "updated_at")


@admin.register(DocumentVersion)
class DocumentVersionAdmin(ReadOnlyAuditAdmin):
    list_display = ("document", "version", "original_name", "is_current", "is_deleted")
    list_filter = ("is_current", "is_deleted")
    readonly_fields = (
        "stored_name",
        "original_name",
        "content_type",
        "size",
        "uploaded_by",
        "created_at",
    )
    fields = (
        "document",
        "version",
        "file",
        "stored_name",
        "original_name",
        "content_type",
        "size",
        "uploaded_by",
        "is_current",
        "is_deleted",
        "created_at",
    )


@admin.register(AttachmentSequence)
class AttachmentSequenceAdmin(ReadOnlyAuditAdmin):
    readonly_fields = ("last_number",)

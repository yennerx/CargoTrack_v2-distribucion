from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier
from apps.core.access_scope import scope_carriers, scope_documents, scope_orders
from apps.orders.models import Order

from .forms import DocumentUploadForm, VersionUploadForm
from .models import Document, DocumentVersion
from .services import (
    delete_version,
    is_administrator,
    restore_version,
    upload_document,
    upload_version,
)


def require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


@login_required
@require_POST
def order_document_upload(request, pk):
    require_permission(request, "documents.add_document")
    order = get_object_or_404(scope_orders(Order.objects.all(), request.user), pk=pk)
    form = DocumentUploadForm(request.POST, request.FILES)
    if form.is_valid():
        upload_document(
            uploaded_file=form.cleaned_data["file"],
            actor=request.user,
            target=order,
            document_data={**form.cleaned_data, "target_type": "order"},
        )
        messages.success(request, "Documento cargado correctamente.")
    else:
        messages.error(request, "No se pudo cargar el documento: revise el archivo y sus datos.")
    return redirect("orders:detail", pk=order.pk)


@login_required
@require_POST
def carrier_document_upload(request, pk):
    require_permission(request, "documents.add_document")
    carrier = get_object_or_404(
        scope_carriers(Carrier.objects.all(), request.user), pk=pk
    )
    form = DocumentUploadForm(request.POST, request.FILES)
    if form.is_valid():
        upload_document(
            uploaded_file=form.cleaned_data["file"],
            actor=request.user,
            target=carrier,
            document_data={**form.cleaned_data, "target_type": "carrier"},
        )
        messages.success(request, "Documento cargado correctamente.")
    else:
        messages.error(request, "No se pudo cargar el documento: revise el archivo y sus datos.")
    return redirect("carriers:detail", pk=carrier.pk)


@login_required
@require_GET
def document_detail(request, pk):
    require_permission(request, "documents.view_document")
    document = get_object_or_404(
        scope_document_queryset(request.user).select_related(
            "document_type", "order", "carrier", "incident", "created_by"
        ),
        pk=pk,
    )
    return render(
        request,
        "documents/document_detail.html",
        {"document": document, "versions": document.versions.select_related("uploaded_by")},
    )


@login_required
@require_POST
def version_upload(request, pk):
    require_permission(request, "documents.add_documentversion")
    document = get_object_or_404(scope_document_queryset(request.user), pk=pk)
    form = VersionUploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            upload_version(
                document=document,
                uploaded_file=form.cleaned_data["file"],
                actor=request.user,
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "Nueva versión cargada correctamente.")
    else:
        messages.error(request, "No se pudo cargar la versión: revise el archivo.")
    return redirect("documents:detail", pk=document.pk)


@login_required
@require_GET
def version_download(request, pk):
    require_permission(request, "documents.view_document")
    version = get_object_or_404(
        DocumentVersion.objects.select_related("document").filter(
            document_id__in=scope_document_queryset(request.user).values("pk")
        ),
        pk=pk,
        is_deleted=False,
    )
    response = FileResponse(
        version.file.open("rb"), as_attachment=True, filename=version.original_name
    )
    AuditEvent.objects.create(
        actor=request.user,
        order=version.document.order
        or (version.document.incident.order if version.document.incident_id else None),
        action="download_document_version",
        entity_type="document",
        entity_id=str(version.document_id),
        metadata={
            "version": version.version,
            "document_type": version.document.document_type.code,
        },
    )
    return response


@login_required
@require_POST
def version_restore(request, pk):
    require_permission(request, "documents.change_documentversion")
    version = get_object_or_404(
        DocumentVersion.objects.select_related("document").filter(
            document_id__in=scope_document_queryset(request.user).values("pk")
        ),
        pk=pk,
    )
    if not is_administrator(request.user):
        raise PermissionDenied
    try:
        restore_version(version=version, actor=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "La versión fue restaurada como vigente.")
    return redirect("documents:detail", pk=version.document_id)


@login_required
@require_POST
def version_delete(request, pk):
    require_permission(request, "documents.delete_documentversion")
    version = get_object_or_404(
        DocumentVersion.objects.select_related("document").filter(
            document_id__in=scope_document_queryset(request.user).values("pk")
        ),
        pk=pk,
    )
    if not is_administrator(request.user):
        raise PermissionDenied
    try:
        delete_version(version=version, actor=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "El archivo fue eliminado y la acción quedó auditada.")
    return redirect("documents:detail", pk=version.document_id)


def scope_document_queryset(user):
    return scope_documents(Document.objects.all(), user)

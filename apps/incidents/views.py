from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.catalogs.models import CatalogEntry, CatalogType
from apps.core.access_scope import scope_assigned_orders, scope_incidents
from apps.documents.forms import DocumentUploadForm
from apps.documents.services import upload_document
from apps.orders.models import Order

from .forms import IncidentForm, IncidentTransitionForm
from .models import Incident, IncidentStatus
from .services import ALLOWED_TRANSITIONS, create_incident, transition_incident


def require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


@login_required
@require_GET
def incident_list(request):
    require_permission(request, "incidents.view_incident")
    incidents = scope_incidents(
        Incident.objects.select_related("order", "incident_type", "priority", "assigned_to"),
        request.user,
    )
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "").strip()
    priority = request.GET.get("priority", "").strip()
    if query:
        incidents = incidents.filter(
            Q(title__icontains=query)
            | Q(order__number__icontains=query)
            | Q(description__icontains=query)
        )
    if status:
        incidents = incidents.filter(status=status)
    if priority:
        incidents = incidents.filter(priority__code=priority)
    page = Paginator(incidents, 25).get_page(request.GET.get("page"))
    return render(
        request,
        "incidents/incident_list.html",
        {
            "incidents": page,
            "page_obj": page,
            "query": query,
            "status": status,
            "priority": priority,
            "status_options": IncidentStatus.choices,
            "priority_options": CatalogEntry.objects.filter(
                catalog_type=CatalogType.INCIDENT_PRIORITY, is_active=True
            ),
        },
    )


@login_required
def incident_create(request, order_pk):
    require_permission(request, "incidents.add_incident")
    order = get_object_or_404(
        scope_assigned_orders(Order.objects.all(), request.user), pk=order_pk
    )
    if request.method == "POST":
        form = IncidentForm(request.POST)
        if form.is_valid():
            incident = create_incident(form=form, order=order, actor=request.user)
            messages.success(request, "Incidencia registrada correctamente.")
            return redirect("incidents:detail", pk=incident.pk)
    else:
        form = IncidentForm()
    return render(
        request,
        "incidents/incident_form.html",
        {"form": form, "order": order, "title": "Nueva incidencia"},
    )


@login_required
@require_GET
def incident_detail(request, pk):
    require_permission(request, "incidents.view_incident")
    incident = get_object_or_404(
        scope_incidents(
            Incident.objects.select_related(
                "order", "incident_type", "priority", "assigned_to"
            ),
            request.user,
        ),
        pk=pk,
    )
    allowed_statuses = ALLOWED_TRANSITIONS.get(incident.status, set())
    return render(
        request,
        "incidents/incident_detail.html",
        {
            "incident": incident,
            "history": incident.history.select_related("changed_by"),
            "transition_form": IncidentTransitionForm(allowed_statuses=allowed_statuses),
            "document_form": DocumentUploadForm(),
            "documents": incident.documents.select_related("document_type").filter(is_active=True),
        },
    )


@login_required
@require_POST
def incident_transition(request, pk):
    require_permission(request, "incidents.change_incident")
    incident = get_object_or_404(
        scope_incidents(Incident.objects.all(), request.user), pk=pk
    )
    allowed_statuses = ALLOWED_TRANSITIONS.get(incident.status, set())
    form = IncidentTransitionForm(request.POST, allowed_statuses=allowed_statuses)
    if form.is_valid():
        try:
            transition_incident(
                incident=incident,
                target_status=form.cleaned_data["status"],
                actor=request.user,
                observation=form.cleaned_data["observation"],
                resolution=form.cleaned_data["resolution"],
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "Estado de incidencia actualizado.")
    else:
        messages.error(request, "Revise el estado, la observación y la resolución.")
    return redirect("incidents:detail", pk=incident.pk)


@login_required
@require_POST
def incident_document_upload(request, pk):
    require_permission(request, "documents.add_document")
    incident = get_object_or_404(
        scope_incidents(Incident.objects.all(), request.user), pk=pk
    )
    form = DocumentUploadForm(request.POST, request.FILES)
    if form.is_valid():
        upload_document(
            uploaded_file=form.cleaned_data["file"],
            actor=request.user,
            target=incident,
            document_data={**form.cleaned_data, "target_type": "incident"},
        )
        messages.success(request, "Evidencia cargada correctamente.")
    else:
        messages.error(request, "No se pudo cargar la evidencia.")
    return redirect("incidents:detail", pk=incident.pk)

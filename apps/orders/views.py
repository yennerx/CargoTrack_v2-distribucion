from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.audit.models import AuditEvent
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.core.access_scope import scope_orders
from apps.documents.forms import DocumentUploadForm
from apps.documents.services import order_closing_document_errors

from .forms import OrderForm, OrderStatusChangeForm
from .models import CLOSURE_CATALOG_CODES, Order, OrderClosureStatus
from .services import (
    allowed_transition_codes,
    create_order,
    order_is_overdue,
    transition_order,
)


def _require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


def _require_dispatcher(request):
    _require_permission(request, "orders.change_order")
    is_dispatcher = request.user.groups.filter(name="Dispatcher").exists()
    if not (request.user.is_superuser or is_dispatcher):
        raise PermissionDenied


@login_required
def order_list(request):
    _require_permission(request, "orders.view_order")
    orders = scope_orders(Order.objects.select_related(
        "status", "customer", "proposed_carrier", "confirmed_carrier"
    ), request.user)
    query = request.GET.get("q", "").strip()
    if query:
        orders = orders.filter(
            Q(number__icontains=query)
            | Q(customer__legal_name__icontains=query)
            | Q(proposed_carrier__legal_name__icontains=query)
            | Q(confirmed_carrier__legal_name__icontains=query)
        )
    status = request.GET.get("status", "").strip()
    if status:
        orders = orders.filter(status__code=status)
    closure_status = request.GET.get("closure", "").strip()
    if closure_status in OrderClosureStatus.values:
        orders = orders.filter(closure_status=closure_status)
    overdue = request.GET.get("atrasadas") == "1"
    overdue_cutoff = timezone.localdate() - timedelta(days=settings.ORDER_OVERDUE_DAYS)
    if overdue:
        orders = orders.exclude(status__code__in=("entregada", "cancelada")).filter(
            updated_at__date__lte=overdue_cutoff
        )
    page = Paginator(orders, 25).get_page(request.GET.get("page"))
    for order in page.object_list:
        order.is_overdue = order_is_overdue(order)
    return render(
        request,
        "orders/order_list.html",
        {
            "orders": page,
            "page_obj": page,
            "query": query,
            "status": status,
            "closure_status": closure_status,
            "overdue": overdue,
            "status_options": CatalogEntry.objects.filter(
                catalog_type=CatalogType.ORDER_STATUS, is_active=True
            ).exclude(code__in=CLOSURE_CATALOG_CODES),
            "closure_status_options": OrderClosureStatus.choices,
        },
    )


@login_required
def order_detail(request, pk):
    _require_permission(request, "orders.view_order")
    order = get_object_or_404(
        scope_orders(Order.objects.select_related(
            "status", "customer", "proposed_carrier", "confirmed_carrier",
            "broker", "dispatcher", "cargo_type", "equipment_type", "confirmed_by",
        ), request.user),
        pk=pk,
    )
    allowed_codes = allowed_transition_codes(order)
    return render(
        request,
        "orders/order_detail.html",
        {
            "order": order,
            "status_history": order.status_history.select_related(
                "previous_status", "status", "changed_by"
            ),
            "status_form": OrderStatusChangeForm(allowed_codes=allowed_codes),
            "document_form": DocumentUploadForm(),
            "documents": order.documents.select_related("document_type").filter(is_active=True),
            "closing_document_errors": (
                order_closing_document_errors(order)
                if order.status.code == "entregada"
                and order.closure_status
                in {OrderClosureStatus.OPEN, OrderClosureStatus.PENDING}
                else []
            ),
            "is_overdue": order_is_overdue(order),
        },
    )


@login_required
def order_create(request):
    _require_permission(request, "orders.add_order")
    if request.method == "POST":
        form = OrderForm(request.POST, actor=request.user)
        if form.is_valid():
            with transaction.atomic():
                order = create_order(form=form, actor=request.user)
                if order.proposed_carrier_id:
                    order.proposed_at = timezone.now()
                    order.save(update_fields=("proposed_at", "updated_at"))
                AuditEvent.objects.create(
                    actor=request.user,
                    order=order,
                    action="create_order",
                    entity_type="order",
                    entity_id=str(order.pk),
                    metadata={
                        "number": order.number,
                        "broker_id": order.broker_id,
                        "created_by_id": order.created_by_id,
                    },
                )
            messages.success(request, "Orden creada correctamente.")
            return redirect("orders:detail", pk=order.pk)
    else:
        form = OrderForm(actor=request.user)
    return render(request, "orders/order_form.html", {"form": form, "title": "Nueva orden"})


@login_required
def order_update(request, pk):
    _require_permission(request, "orders.change_order")
    order = get_object_or_404(
        scope_orders(Order.objects.select_related("status"), request.user), pk=pk
    )
    if order.closure_status == OrderClosureStatus.CLOSED:
        raise PermissionDenied("No se puede editar una orden cerrada.")
    if request.method == "POST":
        previous_broker_id = order.broker_id
        form = OrderForm(request.POST, instance=order, actor=request.user)
        if form.is_valid():
            order = form.save()
            if order.proposed_carrier_id and not order.proposed_at:
                order.proposed_at = timezone.now()
                order.save(update_fields=("proposed_at", "updated_at"))
            AuditEvent.objects.create(
                actor=request.user,
                order=order,
                action="update_order",
                entity_type="order",
                entity_id=str(order.pk),
                metadata={
                    "number": order.number,
                    "broker_id_before": previous_broker_id,
                    "broker_id_after": order.broker_id,
                },
            )
            messages.success(request, "Orden actualizada correctamente.")
            return redirect("orders:detail", pk=order.pk)
    else:
        form = OrderForm(instance=order, actor=request.user)
    return render(
        request,
        "orders/order_form.html",
        {"form": form, "title": "Editar orden", "order": order},
    )


@require_POST
@login_required
def order_confirm_carrier(request, pk):
    _require_dispatcher(request)
    order = get_object_or_404(scope_orders(Order.objects.all(), request.user), pk=pk)
    if order.closure_status == OrderClosureStatus.CLOSED:
        raise PermissionDenied("No se puede modificar una orden cerrada.")
    carrier = order.proposed_carrier
    if not carrier or not carrier.is_active or not carrier.is_validated:
        messages.error(request, "El transportista propuesto debe estar activo y validado.")
        return redirect("orders:detail", pk=order.pk)
    order.confirmed_carrier = carrier
    order.confirmed_by = request.user
    order.confirmed_at = timezone.now()
    order.formalized_by = request.user
    order.formalized_at = timezone.now()
    order.save(
        update_fields=(
            "confirmed_carrier",
            "confirmed_by",
            "confirmed_at",
            "formalized_by",
            "formalized_at",
            "updated_at",
        )
    )
    AuditEvent.objects.create(
        actor=request.user,
        order=order,
        action="confirm_order_carrier",
        entity_type="order",
        entity_id=str(order.pk),
        metadata={"number": order.number, "carrier_id": carrier.pk},
    )
    messages.success(request, "Transportista confirmado correctamente.")
    return redirect("orders:detail", pk=order.pk)


@require_POST
@login_required
def order_change_status(request, pk):
    _require_permission(request, "orders.change_order")
    order = get_object_or_404(
        scope_orders(
            Order.objects.select_related("status"), request.user
        ),
        pk=pk,
    )
    allowed_codes = allowed_transition_codes(order)
    form = OrderStatusChangeForm(request.POST, allowed_codes=allowed_codes)
    if form.is_valid():
        try:
            order = transition_order(
                order=order,
                target_status=form.cleaned_data["status"],
                actor=request.user,
                observation=form.cleaned_data["observation"],
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            AuditEvent.objects.create(
                actor=request.user,
                order=order,
                action="change_order_status",
                entity_type="order",
                entity_id=str(order.pk),
                metadata={
                    "number": order.number,
                    "status": order.status.code,
                    "closure_status": order.closure_status,
                },
            )
            messages.success(request, "Estado actualizado correctamente.")
            return redirect("orders:detail", pk=order.pk)
    else:
        messages.error(request, "Seleccione una transición y revise la observación.")
    return redirect("orders:detail", pk=order.pk)

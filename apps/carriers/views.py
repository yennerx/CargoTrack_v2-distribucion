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
from apps.core.access_scope import is_broker, scope_carriers, scope_orders
from apps.documents.forms import DocumentUploadForm
from apps.finance.models import FinancialTransaction
from apps.orders.models import Order

from .forms import CarrierDocumentFormSet, CarrierForm, CarrierUnitFormSet
from .models import Carrier
from .services import document_is_expiring_soon, validate_carrier


def require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


def carrier_context(carrier):
    carrier_documents = list(carrier.documents.select_related("document_type").all())
    for document in carrier_documents:
        document.is_expired = document.expires_at < timezone.localdate()
        document.is_expiring_soon = document_is_expiring_soon(document)
    return {
        "carrier": carrier,
        "documents": carrier_documents,
        "attachments": carrier.attachments.select_related("document_type").filter(is_active=True),
        "document_form": DocumentUploadForm(),
    }


@login_required
def carrier_list(request):
    require_permission(request, "carriers.view_carrier")
    carriers = scope_carriers(Carrier.objects.all(), request.user)
    query = request.GET.get("q", "").strip()
    if query:
        carriers = carriers.filter(
            Q(nit__icontains=query)
            | Q(legal_name__icontains=query)
            | Q(commercial_name__icontains=query)
        )
    if request.GET.get("inactivos") != "1":
        carriers = carriers.filter(is_active=True)
    return render(request, "carriers/carrier_list.html", {"carriers": carriers, "query": query})


@login_required
def carrier_detail(request, pk):
    require_permission(request, "carriers.view_carrier")
    carrier = get_object_or_404(
        scope_carriers(
            Carrier.objects.prefetch_related("units", "documents__document_type", "brokers"),
            request.user,
        ),
        pk=pk,
    )
    context = carrier_context(carrier)
    can_view_order_history = request.user.has_perm("orders.view_order")
    can_view_payment_history = request.user.has_perm(
        "finance.view_financialtransaction"
    )
    context.update(
        {
            "orders": None,
            "payments": None,
            "can_view_order_history": can_view_order_history,
            "can_view_payment_history": (
                can_view_order_history and can_view_payment_history
            ),
        }
    )
    if can_view_order_history:
        orders = scope_orders(
            Order.objects.filter(confirmed_carrier=carrier).select_related(
                "status", "customer", "broker"
            ),
            request.user,
        )
        context["orders"] = Paginator(orders, 25).get_page(
            request.GET.get("orders_page")
        )
        if can_view_payment_history:
            payments = FinancialTransaction.objects.filter(
                order__in=orders,
                movement_type__code="pago-transportista",
            ).select_related("order", "currency", "created_by")
            context["payments"] = Paginator(payments, 25).get_page(
                request.GET.get("payments_page")
            )
    return render(request, "carriers/carrier_detail.html", context)


@login_required
def carrier_create(request):
    require_permission(request, "carriers.add_carrier")
    if request.method == "POST":
        form = CarrierForm(request.POST, actor=request.user)
        unit_formset = CarrierUnitFormSet(request.POST)
        document_formset = CarrierDocumentFormSet(request.POST)
        if form.is_valid() and unit_formset.is_valid() and document_formset.is_valid():
            with transaction.atomic():
                carrier = form.save(commit=False)
                carrier.created_by = request.user
                carrier.save()
                if is_broker(request.user):
                    carrier.brokers.set((request.user,))
                else:
                    form.save_m2m()
                unit_formset.instance = carrier
                unit_formset.save()
                document_formset.instance = carrier
                document_formset.save()
                AuditEvent.objects.create(
                    actor=request.user,
                    action="create_carrier",
                    entity_type="carrier",
                    entity_id=str(carrier.pk),
                    metadata={
                        "broker_ids": list(carrier.brokers.values_list("pk", flat=True)),
                    },
                )
            messages.success(request, "Transportista creado correctamente.")
            return redirect("carriers:detail", pk=carrier.pk)
    else:
        form = CarrierForm(actor=request.user)
        unit_formset = CarrierUnitFormSet()
        document_formset = CarrierDocumentFormSet()
    return render(
        request,
        "carriers/carrier_form.html",
        {
            "form": form,
            "unit_formset": unit_formset,
            "document_formset": document_formset,
            "title": "Nuevo transportista",
        },
    )


@login_required
def carrier_update(request, pk):
    require_permission(request, "carriers.change_carrier")
    carrier = get_object_or_404(
        scope_carriers(Carrier.objects.all(), request.user), pk=pk
    )
    if request.method == "POST":
        form = CarrierForm(request.POST, instance=carrier, actor=request.user)
        unit_formset = CarrierUnitFormSet(request.POST, instance=carrier)
        document_formset = CarrierDocumentFormSet(request.POST, instance=carrier)
        if form.is_valid() and unit_formset.is_valid() and document_formset.is_valid():
            previous_broker_ids = list(carrier.brokers.values_list("pk", flat=True))
            with transaction.atomic():
                carrier = form.save()
                unit_formset.save()
                document_formset.save()
                AuditEvent.objects.create(
                    actor=request.user,
                    action="update_carrier",
                    entity_type="carrier",
                    entity_id=str(carrier.pk),
                    metadata={
                        "broker_ids_before": previous_broker_ids,
                        "broker_ids_after": list(
                            carrier.brokers.values_list("pk", flat=True)
                        ),
                    },
                )
            messages.success(request, "Transportista actualizado correctamente.")
            return redirect("carriers:detail", pk=carrier.pk)
    else:
        form = CarrierForm(instance=carrier, actor=request.user)
        unit_formset = CarrierUnitFormSet(instance=carrier)
        document_formset = CarrierDocumentFormSet(instance=carrier)
    return render(
        request,
        "carriers/carrier_form.html",
        {
            "form": form,
            "unit_formset": unit_formset,
            "document_formset": document_formset,
            "title": "Editar transportista",
            "carrier": carrier,
        },
    )


@login_required
@require_POST
def carrier_validate(request, pk):
    require_permission(request, "carriers.change_carrier")
    carrier = get_object_or_404(
        scope_carriers(Carrier.objects.all(), request.user), pk=pk
    )
    try:
        validate_carrier(carrier, request.user)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        AuditEvent.objects.create(
            actor=request.user,
            action="validate_carrier",
            entity_type="carrier",
            entity_id=str(carrier.pk),
            metadata={},
        )
        messages.success(request, "Transportista validado correctamente.")
    return redirect("carriers:detail", pk=carrier.pk)


@login_required
@require_POST
def carrier_deactivate(request, pk):
    require_permission(request, "carriers.delete_carrier")
    carrier = get_object_or_404(
        scope_carriers(Carrier.objects.all(), request.user), pk=pk
    )
    carrier.is_active = False
    carrier.save(update_fields=("is_active", "updated_at"))
    AuditEvent.objects.create(
        actor=request.user,
        action="deactivate_carrier",
        entity_type="carrier",
        entity_id=str(carrier.pk),
        metadata={},
    )
    messages.success(request, "Transportista desactivado correctamente.")
    return redirect("carriers:list")

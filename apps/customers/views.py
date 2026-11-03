from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.audit.models import AuditEvent
from apps.core.access_scope import is_broker, scope_customers, scope_orders
from apps.finance.models import FinancialTransaction
from apps.orders.models import Order

from .forms import CustomerContactFormSet, CustomerForm
from .models import Customer


def _require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


@login_required
@require_GET
def customer_list(request):
    _require_permission(request, "customers.view_customer")
    customers = scope_customers(
        Customer.objects.prefetch_related("contacts", "brokers"), request.user
    )
    query = request.GET.get("q", "").strip()
    if query:
        customers = customers.filter(
            Q(nit__icontains=query)
            | Q(legal_name__icontains=query)
            | Q(commercial_name__icontains=query)
        )
    if request.GET.get("inactivos") != "1":
        customers = customers.filter(is_active=True)
    return render(request, "customers/customer_list.html", {"customers": customers, "query": query})


@login_required
@require_GET
def customer_detail(request, pk):
    _require_permission(request, "customers.view_customer")
    customer = get_object_or_404(
        scope_customers(Customer.objects.prefetch_related("contacts", "brokers"), request.user),
        pk=pk,
    )
    order_page = None
    collection_page = None
    can_view_order_history = request.user.has_perm("orders.view_order")
    can_view_collection_history = request.user.has_perm(
        "finance.view_financialtransaction"
    )
    if can_view_order_history:
        orders = scope_orders(
            Order.objects.filter(customer=customer).select_related(
                "status", "confirmed_carrier", "broker"
            ),
            request.user,
        )
        order_page = Paginator(orders, 25).get_page(request.GET.get("orders_page"))
        if can_view_collection_history:
            collections = FinancialTransaction.objects.filter(
                order__in=orders,
                movement_type__code="cobro-cliente",
            ).select_related("order", "currency", "created_by")
            collection_page = Paginator(collections, 25).get_page(
                request.GET.get("collections_page")
            )
    return render(
        request,
        "customers/customer_detail.html",
        {
            "customer": customer,
            "orders": order_page,
            "collections": collection_page,
            "can_view_order_history": can_view_order_history,
            "can_view_collection_history": (
                can_view_order_history and can_view_collection_history
            ),
        },
    )


@login_required
def customer_create(request):
    _require_permission(request, "customers.add_customer")
    if request.method == "POST":
        form = CustomerForm(request.POST, actor=request.user)
        formset = CustomerContactFormSet(request.POST)
        if form.is_valid() and formset.is_valid():
            with transaction.atomic():
                customer = form.save(commit=False)
                customer.created_by = request.user
                customer.save()
                if is_broker(request.user):
                    customer.brokers.set((request.user,))
                else:
                    form.save_m2m()
                formset.instance = customer
                formset.save()
                AuditEvent.objects.create(
                    actor=request.user,
                    action="create_customer",
                    entity_type="customer",
                    entity_id=str(customer.pk),
                    metadata={
                        "broker_ids": list(customer.brokers.values_list("pk", flat=True)),
                    },
                )
            messages.success(request, "Cliente creado correctamente.")
            return redirect("customers:detail", pk=customer.pk)
    else:
        form = CustomerForm(actor=request.user)
        formset = CustomerContactFormSet()
    return render(
        request,
        "customers/customer_form.html",
        {"form": form, "formset": formset, "title": "Nuevo cliente"},
    )


@login_required
def customer_update(request, pk):
    _require_permission(request, "customers.change_customer")
    customer = get_object_or_404(
        scope_customers(Customer.objects.all(), request.user), pk=pk
    )
    if request.method == "POST":
        form = CustomerForm(request.POST, instance=customer, actor=request.user)
        formset = CustomerContactFormSet(request.POST, instance=customer)
        if form.is_valid() and formset.is_valid():
            previous_broker_ids = list(customer.brokers.values_list("pk", flat=True))
            with transaction.atomic():
                customer = form.save()
                formset.save()
                AuditEvent.objects.create(
                    actor=request.user,
                    action="update_customer",
                    entity_type="customer",
                    entity_id=str(customer.pk),
                    metadata={
                        "broker_ids_before": previous_broker_ids,
                        "broker_ids_after": list(
                            customer.brokers.values_list("pk", flat=True)
                        ),
                    },
                )
            messages.success(request, "Cliente actualizado correctamente.")
            return redirect("customers:detail", pk=customer.pk)
    else:
        form = CustomerForm(instance=customer, actor=request.user)
        formset = CustomerContactFormSet(instance=customer)
    return render(
        request,
        "customers/customer_form.html",
        {"form": form, "formset": formset, "title": "Editar cliente", "customer": customer},
    )


@require_POST
@login_required
def customer_deactivate(request, pk):
    _require_permission(request, "customers.change_customer")
    customer = get_object_or_404(
        scope_customers(Customer.objects.all(), request.user), pk=pk
    )
    customer.is_active = False
    customer.save(update_fields=("is_active", "updated_at"))
    AuditEvent.objects.create(
        actor=request.user,
        action="deactivate_customer",
        entity_type="customer",
        entity_id=str(customer.pk),
        metadata={},
    )
    messages.success(request, "Cliente desactivado correctamente.")
    return redirect("customers:list")

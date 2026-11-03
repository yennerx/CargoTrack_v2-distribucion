from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.core.access_scope import scope_orders
from apps.orders.models import Order

from .forms import AuditEventFilterForm
from .models import AuditEvent


@login_required
@require_GET
def event_list(request):
    return _render_event_list(request)


@login_required
@require_GET
def order_history(request, order_pk):
    if not request.user.has_perm("audit.view_auditevent"):
        raise PermissionDenied
    if not request.user.has_perm("orders.view_order"):
        raise PermissionDenied
    order = get_object_or_404(
        scope_orders(Order.objects.all(), request.user), pk=order_pk
    )
    return _render_event_list(request, order=order)


def _render_event_list(request, *, order=None):
    if not request.user.has_perm("audit.view_auditevent"):
        raise PermissionDenied

    filter_form = AuditEventFilterForm(request.GET or None)
    filters_valid = not filter_form.is_bound or filter_form.is_valid()
    filters = filter_form.cleaned_data if filter_form.is_bound and filters_valid else {}
    events = (
        AuditEvent.objects.select_related("actor", "order")
        if filters_valid
        else AuditEvent.objects.none()
    )
    if order and filters_valid:
        events = events.filter(order=order)
    if filters.get("action"):
        events = events.filter(action=filters["action"])
    if filters.get("entity_type"):
        events = events.filter(entity_type=filters["entity_type"])
    if filters.get("actor"):
        events = events.filter(actor=filters["actor"])
    if filters.get("date_from"):
        events = events.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        events = events.filter(created_at__date__lte=filters["date_to"])

    page = Paginator(events, 50).get_page(request.GET.get("page"))
    query_parameters = request.GET.copy()
    query_parameters.pop("page", None)
    pagination_query = query_parameters.urlencode()
    return render(
        request,
        "audit/event_list.html",
        {
            "page": page,
            "filter_form": filter_form,
            "filters_valid": filters_valid,
            "pagination_query": pagination_query,
            "order": order,
            "can_view_orders": request.user.has_perm("orders.view_order"),
            "list_url": (
                reverse("audit:order_history", args=(order.pk,))
                if order
                else reverse("audit:list")
            ),
        },
    )

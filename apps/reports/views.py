from urllib.parse import urlencode

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.shortcuts import render
from django.urls import reverse

from .admin_forms import (
    ADMIN_REPORT_PERMISSIONS,
    ADMIN_REPORTS,
    AdministrativeReportFilterForm,
)
from .admin_services import (
    administrative_csv_response,
    administrative_report_queryset,
    available_administrative_reports,
)
from .forms import (
    LEGACY_REPORT_PRESETS,
    ORDER_REPORT_SHORTCUTS,
    REPORT_CHOICES,
    ReportFilterForm,
)
from .services import (
    FINANCIAL_REPORTS,
    can_export_reports,
    csv_response,
    dashboard_metrics,
    is_financial_report_user,
    report_page_size,
    report_queryset,
)


def require_orders_report_permission(request):
    if not request.user.has_perm("orders.view_order"):
        raise PermissionDenied


@login_required
def dashboard(request):
    require_orders_report_permission(request)
    metrics = dashboard_metrics({}, user=request.user)
    if not is_financial_report_user(request.user) and metrics is not None:
        metrics = {
            "active_orders": metrics["active_orders"],
            "overdue_orders": metrics["overdue_orders"],
        }
    quick_access = [
        {
            "label": label,
            "url": f"{reverse('reports:detail', args=('orders',))}?{urlencode(filters)}",
        }
        for label, filters in ORDER_REPORT_SHORTCUTS
    ]
    return render(
        request,
        "reports/dashboard.html",
        {
            "metrics": metrics,
            "financial_access": is_financial_report_user(request.user),
            "report_choices": REPORT_CHOICES,
            "financial_reports": FINANCIAL_REPORTS,
            "quick_access": quick_access,
            "administrative_reports": available_administrative_reports(request.user),
        },
    )


@login_required
def report_detail(request, report_type):
    if report_type in dict(ADMIN_REPORTS):
        return administrative_report_detail(request, report_type)

    require_orders_report_permission(request)
    canonical_type = "orders" if report_type in LEGACY_REPORT_PRESETS else report_type
    if canonical_type not in dict(REPORT_CHOICES):
        raise PermissionDenied
    if canonical_type in FINANCIAL_REPORTS and not is_financial_report_user(request.user):
        raise PermissionDenied
    query = request.GET.copy()
    for key, value in LEGACY_REPORT_PRESETS.get(report_type, {}).items():
        query.setdefault(key, value)
    query["report"] = canonical_type
    if canonical_type == "orders":
        query.setdefault("date_basis", "created")
    form = ReportFilterForm(query, user=request.user)
    filters_valid = form.is_valid()
    filters = form.cleaned_data if filters_valid else None
    export_allowed = can_export_reports(request.user)
    query_params = query.copy()
    query_params.pop("page", None)
    query_params.pop("format", None)
    export_params = query_params.copy()
    export_params["format"] = "csv"
    commission_summary_params = query_params.copy()
    commission_summary_params.pop("broker", None)

    if request.GET.get("format") == "csv":
        if not export_allowed:
            raise PermissionDenied
        if filters_valid:
            rows = report_queryset(canonical_type, filters, user=request.user)
            return csv_response(canonical_type, list(rows[:1000]), request.user, filters)

    rows = (
        report_queryset(canonical_type, filters, user=request.user)
        if filters_valid
        else []
    )
    page = Paginator(rows, report_page_size()).get_page(request.GET.get("page"))
    order_groups = []
    group_by = filters.get("group_by") if filters_valid and canonical_type == "orders" else ""
    commission_detail_mode = bool(
        canonical_type == "commissions" and filters_valid and filters.get("broker")
    )
    if canonical_type == "commissions" and filters_valid and not commission_detail_mode:
        for row in page.object_list:
            drilldown_params = query_params.copy()
            drilldown_params["broker"] = str(row["broker_id"])
            row["detail_url"] = (
                f"{reverse('reports:detail', args=('commissions',))}?"
                f"{drilldown_params.urlencode()}"
            )
    commission_summary_url = ""
    if canonical_type == "commissions" and commission_detail_mode:
        commission_summary_url = (
            f"{reverse('reports:detail', args=('commissions',))}?"
            f"{commission_summary_params.urlencode()}"
        )
    period_basis_label = {
        "orders": "fecha de creación o entrega seleccionada",
        "commissions": "fecha de cálculo de la comisión",
        "financial-summary": "fecha del movimiento financiero",
        "pending-collections": "fecha del movimiento financiero",
        "pending-payments": "fecha del movimiento financiero",
    }.get(canonical_type, "fecha")
    if group_by:
        grouped = {}
        for row in page.object_list:
            grouped.setdefault(row.report_group_label or "Sin asignación", []).append(row)
        order_groups = [{"label": label, "rows": items} for label, items in grouped.items()]
    return render(
        request,
        "reports/report_detail.html",
        {
            "form": form,
            "report_type": canonical_type,
            "report_title": dict(REPORT_CHOICES)[canonical_type],
            "rows": page,
            "page_obj": page,
            "export_allowed": export_allowed,
            "filters_valid": filters_valid,
            "filter_querystring": query_params.urlencode(),
            "export_querystring": export_params.urlencode(),
            "report_group_by": group_by,
            "order_groups": order_groups,
            "commission_detail_mode": commission_detail_mode,
            "commission_summary_url": commission_summary_url,
            "period_basis_label": period_basis_label,
            "overdue_description": (
                f"Atraso: orden no entregada ni cancelada sin actualización durante "
                f"{settings.ORDER_OVERDUE_DAYS} días."
                if canonical_type == "orders"
                else ""
            ),
        },
        status=200 if filters_valid else 400,
    )


def administrative_report_detail(request, report_type):
    permission = ADMIN_REPORT_PERMISSIONS[report_type]
    if not request.user.has_perm(permission):
        raise PermissionDenied

    form = AdministrativeReportFilterForm(
        request.GET, report_type=report_type, user=request.user
    )
    filters_valid = form.is_valid()
    filters = form.cleaned_data if filters_valid else None
    export_allowed = can_export_reports(request.user)
    query_params = request.GET.copy()
    query_params.pop("page", None)
    query_params.pop("format", None)
    export_params = query_params.copy()
    export_params["format"] = "csv"

    if request.GET.get("format") == "csv":
        if not export_allowed:
            raise PermissionDenied
        if filters_valid:
            rows = administrative_report_queryset(report_type, filters, user=request.user)
            return administrative_csv_response(
                report_type,
                list(rows[:1000]),
                request.user,
                filters,
            )

    rows = (
        administrative_report_queryset(report_type, filters, user=request.user)
        if filters_valid
        else []
    )
    page = Paginator(rows, report_page_size()).get_page(request.GET.get("page"))
    return render(
        request,
        "reports/admin_report_detail.html",
        {
            "form": form,
            "report_type": report_type,
            "report_title": dict(ADMIN_REPORTS)[report_type],
            "rows": page,
            "page_obj": page,
            "filters_valid": filters_valid,
            "export_allowed": export_allowed,
            "filter_querystring": query_params.urlencode(),
            "export_querystring": export_params.urlencode(),
        },
        status=200 if filters_valid else 400,
    )

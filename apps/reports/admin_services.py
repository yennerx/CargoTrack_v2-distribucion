import csv
from io import StringIO

from django.contrib.auth import get_user_model
from django.db.models import Q
from django.http import HttpResponse

from apps.audit.models import AuditEvent
from apps.audit.services import audit_filter_metadata
from apps.carriers.models import Carrier
from apps.core.access_scope import scope_carriers, scope_customers, scope_incidents
from apps.customers.models import Customer
from apps.incidents.models import Incident

from .admin_forms import ADMIN_REPORT_PERMISSIONS, ADMIN_REPORTS

CSV_ROW_LIMIT = 1000


def available_administrative_reports(user):
    return [
        (report_type, label)
        for report_type, label in ADMIN_REPORTS
        if user.has_perm(ADMIN_REPORT_PERMISSIONS[report_type])
    ]


def _date_range(queryset, filters, field):
    if filters.get("date_from"):
        queryset = queryset.filter(**{f"{field}__date__gte": filters["date_from"]})
    if filters.get("date_to"):
        queryset = queryset.filter(**{f"{field}__date__lte": filters["date_to"]})
    return queryset


def administrative_report_queryset(report_type, filters, *, user=None):
    query = filters.get("query", "").strip()
    if report_type == "users":
        rows = get_user_model().objects.prefetch_related("groups").order_by(
            "-date_joined", "username"
        )
        rows = _date_range(rows, filters, "date_joined")
        if filters.get("is_active"):
            rows = rows.filter(is_active=filters["is_active"] == "active")
        if filters.get("group"):
            rows = rows.filter(groups=filters["group"])
        if query:
            rows = rows.filter(
                Q(username__icontains=query)
                | Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
            )
        return rows.distinct()

    if report_type == "customers":
        rows = Customer.objects.select_related("created_by").order_by(
            "legal_name", "nit"
        )
        if user is not None:
            rows = scope_customers(rows, user)
        rows = _date_range(rows, filters, "created_at")
        if filters.get("is_active"):
            rows = rows.filter(is_active=filters["is_active"] == "active")
        if query:
            rows = rows.filter(
                Q(legal_name__icontains=query)
                | Q(commercial_name__icontains=query)
                | Q(nit__icontains=query)
                | Q(city__icontains=query)
            )
        return rows

    if report_type == "carriers":
        rows = Carrier.objects.select_related("created_by", "validated_by").order_by(
            "legal_name", "nit"
        )
        if user is not None:
            rows = scope_carriers(rows, user)
        rows = _date_range(rows, filters, "created_at")
        if filters.get("is_active"):
            rows = rows.filter(is_active=filters["is_active"] == "active")
        if filters.get("carrier_type"):
            rows = rows.filter(carrier_type=filters["carrier_type"])
        if filters.get("is_validated"):
            rows = rows.filter(is_validated=filters["is_validated"] == "yes")
        if query:
            rows = rows.filter(
                Q(legal_name__icontains=query)
                | Q(commercial_name__icontains=query)
                | Q(nit__icontains=query)
                | Q(city__icontains=query)
            )
        return rows

    if report_type == "incidents":
        rows = Incident.objects.select_related(
            "order__customer", "incident_type", "priority", "assigned_to"
        ).order_by("-created_at")
        if user is not None:
            rows = scope_incidents(rows, user)
        rows = _date_range(rows, filters, "created_at")
        if filters.get("incident_status"):
            rows = rows.filter(status=filters["incident_status"])
        if filters.get("priority"):
            rows = rows.filter(priority=filters["priority"])
        if filters.get("incident_type"):
            rows = rows.filter(incident_type=filters["incident_type"])
        if filters.get("assigned_to"):
            rows = rows.filter(assigned_to=filters["assigned_to"])
        if query:
            rows = rows.filter(
                Q(title__icontains=query)
                | Q(description__icontains=query)
                | Q(order__number__icontains=query)
                | Q(order__customer__legal_name__icontains=query)
            )
        return rows

    raise ValueError(f"Tipo de reporte administrativo no soportado: {report_type}")


def _csv_safe(value):
    if isinstance(value, str) and value.lstrip().startswith(
        ("=", "+", "-", "@", "\t", "\r")
    ):
        return f"'{value}"
    return value


def administrative_csv_response(report_type, rows, actor, filters):
    output = StringIO()
    writer = csv.writer(output)
    if report_type == "users":
        writer.writerow(("Usuario", "Nombre", "Roles", "Habilitado", "Creado", "Último acceso"))
        for row in rows[:CSV_ROW_LIMIT]:
            writer.writerow(
                (
                    _csv_safe(row.username),
                    _csv_safe(row.get_full_name()),
                    _csv_safe(", ".join(group.name for group in row.groups.all())),
                    "Sí" if row.is_active else "No",
                    row.date_joined,
                    row.last_login or "",
                )
            )
    elif report_type == "customers":
        writer.writerow(
            ("NIT", "Razón social", "Nombre comercial", "Ciudad", "Habilitado", "Creado")
        )
        for row in rows[:CSV_ROW_LIMIT]:
            writer.writerow(
                (
                    _csv_safe(row.nit),
                    _csv_safe(row.legal_name),
                    _csv_safe(row.commercial_name),
                    _csv_safe(row.city),
                    "Sí" if row.is_active else "No",
                    row.created_at,
                )
            )
    elif report_type == "carriers":
        writer.writerow(("NIT", "Nombre", "Tipo", "Ciudad", "Habilitado", "Validado", "Creado"))
        for row in rows[:CSV_ROW_LIMIT]:
            writer.writerow(
                (
                    _csv_safe(row.nit),
                    _csv_safe(row.legal_name),
                    row.get_carrier_type_display(),
                    _csv_safe(row.city),
                    "Sí" if row.is_active else "No",
                    "Sí" if row.is_validated else "No",
                    row.created_at,
                )
            )
    else:
        writer.writerow(
            (
                "Orden",
                "Cliente",
                "Incidencia",
                "Tipo",
                "Prioridad",
                "Estado",
                "Responsable",
                "Creada",
            )
        )
        for row in rows[:CSV_ROW_LIMIT]:
            writer.writerow(
                (
                    row.order.number,
                    _csv_safe(row.order.customer.legal_name),
                    _csv_safe(row.title),
                    _csv_safe(row.incident_type.name),
                    _csv_safe(row.priority.name),
                    row.get_status_display(),
                    _csv_safe(row.assigned_to.get_username() if row.assigned_to else ""),
                    row.created_at,
                )
            )

    audit_filters = audit_filter_metadata(filters)
    AuditEvent.objects.create(
        actor=actor,
        action="export_report",
        entity_type="report",
        entity_id=f"admin-{report_type}",
        metadata={"filters": audit_filters, "search_used": bool(filters.get("query"))},
    )
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="cargotrack-{report_type}.csv"'
    )
    return response

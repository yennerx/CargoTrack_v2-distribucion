import json
import logging

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from .dashboard import available_widgets, dashboard_context
from .models import UserDashboardPreference, UserNavigationPreference

logger = logging.getLogger(__name__)

MODULE_ROUTES = {
    "clientes": "customers:list",
    "transportistas": "carriers:list",
    "configuracion": "catalogs:dashboard",
    "ordenes": "orders:list",
    "incidencias": "incidents:list",
    "finanzas": "finance:list",
    "comisiones": "finance:commission-list",
    "reportes": "reports:dashboard",
    "auditoria": "audit:list",
}

MODULES = {
    "clientes": {
        "label": "Clientes",
        "description": "Administración de clientes",
        "section": "Operación",
        "status": "Disponible",
        "permission": "customers.view_customer",
    },
    "transportistas": {
        "label": "Transportistas",
        "description": "Transportistas y documentación vigente",
        "section": "Operación",
        "status": "Disponible",
        "permission": "carriers.view_carrier",
    },
    "ordenes": {
        "label": "Órdenes",
        "description": "Seguimiento de órdenes de despacho",
        "section": "Operación",
        "status": "Disponible",
        "permission": "orders.view_order",
    },
    "incidencias": {
        "label": "Incidencias",
        "description": "Eventos y seguimiento operativo",
        "section": "Operación",
        "status": "Disponible",
        "permission": "incidents.view_incident",
    },
    "finanzas": {
        "label": "Finanzas",
        "description": "Cobros, pagos y gastos",
        "section": "Control",
        "status": "Disponible",
        "permission": "finance.view_financialtransaction",
    },
    "comisiones": {
        "label": "Comisiones",
        "description": "Utilidad, comisiones y cargos",
        "section": "Control",
        "status": "Disponible",
        "permission": "finance.view_commission",
    },
    "reportes": {
        "label": "Reportes",
        "description": "Indicadores y consultas",
        "section": "Control",
        "status": "Disponible",
        "permission": "orders.view_order",
    },
    "auditoria": {
        "label": "Auditoría",
        "description": "Trazabilidad de acciones críticas",
        "section": "Sistema",
        "status": "Disponible",
        "permission": "audit.view_auditevent",
    },
    "configuracion": {
        "label": "Configuración",
        "description": "Parámetros y catálogos",
        "section": "Sistema",
        "status": "Disponible",
        "permission": "catalogs.view_catalogentry",
    },
}


def navigation_sections():
    return {slugify(module["section"]) for module in MODULES.values()} | {"principal"}


@login_required
@require_GET
def home(request):
    return render(
        request,
        "core/home.html",
        dashboard_context(request.user),
    )


@login_required
@require_GET
def module_placeholder(request, module_slug):
    module = MODULES.get(module_slug)
    if module is None:
        raise Http404
    permission = module.get("permission")
    if permission and not request.user.has_perm(permission):
        raise PermissionDenied
    return render(request, "core/module_placeholder.html", {"module": module})


@login_required
@require_POST
def save_navigation_preference(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Formato de preferencias inválido."}, status=400)

    if not isinstance(data, dict):
        return JsonResponse({"error": "Preferencias de navegación inválidas."}, status=400)

    collapsed_sections = data.get("collapsed_sections")
    sidebar_collapsed = data.get("sidebar_collapsed")
    if (
        not isinstance(collapsed_sections, list)
        or any(
            not isinstance(section, str) or section not in navigation_sections()
            for section in collapsed_sections
        )
        or not isinstance(sidebar_collapsed, bool)
    ):
        return JsonResponse({"error": "Preferencias de navegación inválidas."}, status=400)

    preference, _created = UserNavigationPreference.objects.get_or_create(user=request.user)
    preference.collapsed_sections = sorted(set(collapsed_sections))
    preference.sidebar_collapsed = sidebar_collapsed
    preference.save(update_fields=("collapsed_sections", "sidebar_collapsed", "updated_at"))
    return JsonResponse({"saved": True})


@login_required
@require_POST
def save_dashboard_preference(request):
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({"error": "Formato de preferencias inválido."}, status=400)

    if not isinstance(data, dict) or set(data) != {"widget_order", "visible_widgets"}:
        return JsonResponse({"error": "Preferencias del panel inválidas."}, status=400)

    widget_order = data["widget_order"]
    visible_widgets = data["visible_widgets"]
    allowed_widgets = set(available_widgets(request.user))
    if (
        not isinstance(widget_order, list)
        or any(not isinstance(widget, str) for widget in widget_order)
        or len(widget_order) != len(set(widget_order))
        or set(widget_order) != allowed_widgets
        or not isinstance(visible_widgets, list)
        or any(not isinstance(widget, str) for widget in visible_widgets)
        or len(visible_widgets) != len(set(visible_widgets))
        or not visible_widgets
        or not set(visible_widgets).issubset(allowed_widgets)
    ):
        return JsonResponse({"error": "Preferencias del panel inválidas."}, status=400)

    preference, _created = UserDashboardPreference.objects.get_or_create(user=request.user)
    preference.widget_order = widget_order
    preference.visible_widgets = visible_widgets
    preference.save(update_fields=("widget_order", "visible_widgets", "updated_at"))
    return JsonResponse({"saved": True})


@require_GET
def health_check(request):
    return JsonResponse({"status": "ok", "service": "cargotrack"})


def bad_request(request, exception):
    return render(request, "errors/400.html", status=400)


def forbidden(request, exception):
    return render(request, "errors/403.html", status=403)


def page_not_found(request, exception):
    return render(request, "errors/404.html", status=404)


def server_error(request):
    logger.error("Error interno no controlado en la aplicación")
    return render(request, "errors/500.html", status=500)

from django.urls import reverse
from django.utils.text import slugify

from .models import UserNavigationPreference
from .views import MODULE_ROUTES, MODULES

MODULE_ROUTE_NAMES = {
    "clientes": {"list", "create", "detail", "update", "deactivate"},
    "transportistas": {"list", "create", "detail", "update", "validate", "deactivate"},
    "ordenes": {
        "list", "create", "detail", "update", "confirm_carrier", "change_status"
    },
    "incidencias": {"list", "create", "detail", "transition", "upload_document"},
    "finanzas": {"list", "order", "create", "confirm", "adjustment", "validate"},
    "comisiones": {
        "commission-list", "commission-rules", "commission-rule-create", "commission-rule-edit",
        "commission-calculate", "commission-detail", "commission-loss", "commission-authorize",
        "commission-pay", "debt-apply",
    },
    "reportes": {"dashboard", "detail"},
    "auditoria": {"list"},
    "configuracion": {"dashboard"},
    "admin": set(),
}


def navigation(request):
    if not request.user.is_authenticated:
        return {"navigation_items": [], "navigation_sections": []}

    preference = UserNavigationPreference.objects.filter(user=request.user).first()
    collapsed_sections = set(preference.collapsed_sections) if preference else set()

    items = [
        {
            "label": "Inicio",
            "section": "Principal",
            "url": reverse("core:home"),
            "slug": "home",
            "icon": "home",
            "status": "Disponible",
        }
    ]
    for slug, module in MODULES.items():
        permission = module.get("permission")
        if permission and not request.user.has_perm(permission):
            continue
        url = (
            reverse(MODULE_ROUTES[slug])
            if slug in MODULE_ROUTES
            else reverse("core:module-placeholder", args=[slug])
        )
        items.append(
            {
                **module,
                "slug": slug,
                "icon": slug,
                "url": url,
            }
        )

    if request.user.is_staff:
        items.append(
            {
                "label": "Administración",
                "description": "Usuarios, grupos y permisos",
                "section": "Sistema",
                "status": "Disponible",
                "slug": "admin",
                "icon": "admin",
                "url": reverse("admin:index"),
            }
        )
    sections = []
    for item in items:
        section = next(
            (current for current in sections if current["name"] == item["section"]),
            None,
        )
        item["section_slug"] = slugify(item["section"])
        if section is None:
            section = {
                "name": item["section"],
                "slug": item["section_slug"],
                "items": [],
                "active": False,
                "collapsed": item["section_slug"] in collapsed_sections,
            }
            sections.append(section)
        match = request.resolver_match
        item["active"] = request.path == item["url"] or bool(
            match
            and match.namespace
            and (
                (item["slug"] == "admin" and match.namespace == "admin")
                or (
                    match.url_name in MODULE_ROUTE_NAMES.get(item["slug"], set())
                    and MODULE_ROUTES.get(item["slug"], "").split(":", maxsplit=1)[0]
                    == match.namespace
                )
            )
        )
        section["items"].append(item)
        section["active"] = section["active"] or item["active"]

    return {
        "navigation_items": items,
        "navigation_sections": sections,
        "sidebar_collapsed": preference.sidebar_collapsed if preference else False,
    }

from django.urls import reverse

from apps.reports.services import dashboard_metrics, is_financial_report_user

ROLE_DEFAULT_WIDGETS = {
    "Broker": ("active_orders", "overdue_orders"),
    "Dispatcher": (
        "active_orders",
        "overdue_orders",
        "pending_collections",
        "pending_payments",
    ),
    "Gerente administrativo": (
        "active_orders",
        "overdue_orders",
        "profit_usd",
        "pending_commissions",
        "pending_debts",
    ),
    "Gerente general": (
        "active_orders",
        "overdue_orders",
        "profit_usd",
        "pending_commissions",
        "pending_debts",
    ),
    "Administrador": (
        "active_orders",
        "overdue_orders",
        "pending_collections",
        "pending_payments",
        "profit_usd",
        "pending_commissions",
        "pending_debts",
    ),
}

WIDGETS = {
    "active_orders": {
        "title": "Órdenes activas",
        "metric": "active_orders",
        "permission": "orders.view_order",
        "url_name": "reports:detail",
        "url_args": ("orders",),
    },
    "overdue_orders": {
        "title": "Órdenes atrasadas",
        "metric": "overdue_orders",
        "permission": "orders.view_order",
        "url_name": "reports:detail",
        "url_args": ("orders-overdue",),
    },
    "pending_collections": {
        "title": "Cobros pendientes",
        "metric": "pending_collections",
        "permission": "finance.view_financialtransaction",
        "financial": True,
        "url_name": "reports:detail",
        "url_args": ("pending-collections",),
    },
    "pending_payments": {
        "title": "Pagos pendientes",
        "metric": "pending_payments",
        "permission": "finance.view_financialtransaction",
        "financial": True,
        "url_name": "reports:detail",
        "url_args": ("pending-payments",),
    },
    "profit_usd": {
        "title": "Utilidad acumulada (USD)",
        "metric": "profit_usd",
        "permission": "finance.view_financialtransaction",
        "financial": True,
        "format": "currency",
        "url_name": "reports:detail",
        "url_args": ("financial-summary",),
    },
    "pending_commissions": {
        "title": "Comisiones pendientes",
        "metric": "pending_commissions",
        "permission": "finance.view_commission",
        "financial": True,
        "url_name": "reports:detail",
        "url_args": ("commissions",),
    },
    "pending_debts": {
        "title": "Deudas aplicables a comisiones",
        "metric": "pending_debts",
        "permission": "finance.view_brokerdebt",
        "financial": True,
        "url_name": "reports:detail",
        "url_args": ("commissions",),
    },
}


def default_widget_ids(user):
    if user.is_superuser:
        return list(ROLE_DEFAULT_WIDGETS["Administrador"])

    group_names = set(user.groups.values_list("name", flat=True))
    defaults = []
    for role, widget_ids in ROLE_DEFAULT_WIDGETS.items():
        if role in group_names:
            defaults.extend(widget_ids)
    if not defaults and user.has_perm("orders.view_order"):
        defaults.extend(ROLE_DEFAULT_WIDGETS["Broker"])
        if is_financial_report_user(user):
            defaults.extend(
                widget_id
                for widget_id in ROLE_DEFAULT_WIDGETS["Dispatcher"]
                if widget_id not in defaults
            )
    return list(dict.fromkeys(defaults))


def available_widgets(user):
    financial_access = is_financial_report_user(user)
    defaults = default_widget_ids(user)
    widget_ids = list(dict.fromkeys((*defaults, *WIDGETS)))
    return [
        widget_id
        for widget_id in widget_ids
        if user.has_perm("orders.view_order")
        and user.has_perm(WIDGETS[widget_id]["permission"])
        and (not WIDGETS[widget_id].get("financial") or financial_access)
    ]


def dashboard_context(user):
    widget_ids = available_widgets(user)
    preference = getattr(user, "dashboard_preference", None)
    defaults = [widget_id for widget_id in default_widget_ids(user) if widget_id in widget_ids]

    if preference:
        stored_order = preference.widget_order
        stored_visible = preference.visible_widgets
    else:
        stored_order = defaults
        stored_visible = defaults

    valid_order = [
        widget_id
        for widget_id in stored_order
        if isinstance(widget_id, str) and widget_id in widget_ids
    ] if isinstance(stored_order, list) else []
    widget_order = list(dict.fromkeys((*valid_order, *widget_ids)))
    visible_widgets = [
        widget_id
        for widget_id in stored_visible
        if isinstance(widget_id, str) and widget_id in widget_ids
    ] if isinstance(stored_visible, list) else []
    visible_widgets = list(dict.fromkeys(visible_widgets))
    if not visible_widgets:
        visible_widgets = defaults or widget_order[:1]

    metrics = dashboard_metrics({}, user=user) if user.has_perm("orders.view_order") else {}
    widgets = []
    for widget_id in widget_order:
        definition = WIDGETS[widget_id]
        value = metrics.get(definition["metric"])
        widgets.append(
            {
                "id": widget_id,
                "title": definition["title"],
                "value": value,
                "format": definition.get("format", "number"),
                "url": reverse(definition["url_name"], args=definition["url_args"]),
                "visible": widget_id in visible_widgets,
            }
        )

    return {
        "dashboard_widgets": widgets,
        "dashboard_widget_ids": widget_order,
        "dashboard_visible_widgets": visible_widgets,
        "dashboard_preference_url": reverse("core:save-dashboard-preference"),
        "dashboard_metrics_available": bool(metrics),
    }

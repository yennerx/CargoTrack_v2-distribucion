import csv
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.conf import settings
from django.db.models import (
    Case,
    CharField,
    Count,
    DecimalField,
    Exists,
    ExpressionWrapper,
    F,
    OuterRef,
    Q,
    Subquery,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce, Greatest
from django.http import HttpResponse
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import audit_filter_metadata
from apps.catalogs.models import SystemConfiguration
from apps.core.access_scope import scope_orders
from apps.finance.models import (
    CommercialAdjustment,
    CommercialAdjustmentStatus,
    CommercialAdjustmentTarget,
    CommissionDebtApplication,
    CommissionStatus,
    FinancialStatus,
    FinancialTransaction,
)
from apps.orders.models import Order

FINANCIAL_REPORTS = {
    "pending-collections",
    "pending-payments",
    "commissions",
    "financial-summary",
}
EXPORT_GROUPS = {"Administrador", "Gerente administrativo", "Gerente general"}


def is_financial_report_user(user):
    return user.has_perm("finance.view_financialtransaction") and (
        user.is_superuser
        or user.groups.filter(
            name__in=(
                "Administrador",
                "Dispatcher",
                "Gerente administrativo",
                "Gerente general",
            )
        ).exists()
    )


def can_export_reports(user):
    return user.is_superuser or user.groups.filter(name__in=EXPORT_GROUPS).exists()


def report_page_size():
    configured = SystemConfiguration.objects.filter(
        key="report-page-size", is_active=True
    ).values_list("value", flat=True).first()
    try:
        return min(max(int(configured), 1), 100) if configured else 25
    except (TypeError, ValueError):
        return 25


def _date_filters(filters, field):
    values = {}
    if filters.get("date_from"):
        values[f"{field}__gte"] = filters["date_from"]
    if filters.get("date_to"):
        values[f"{field}__lte"] = filters["date_to"]
    return values


def filtered_orders(filters, date_field=None, *, user=None):
    if date_field is None:
        date_field = (
            "delivery_date"
            if filters.get("date_basis") == "delivery"
            else "created_at__date"
        )
    orders = Order.objects.select_related(
        "status",
        "customer",
        "proposed_carrier",
        "confirmed_carrier",
        "broker",
        "cargo_type",
    )
    if user is not None:
        orders = scope_orders(orders, user)
    if filters.get("date_from") or filters.get("date_to"):
        orders = orders.filter(**_date_filters(filters, date_field))
    if filters.get("customer"):
        orders = orders.filter(customer_id=filters["customer"].pk)
    if filters.get("broker"):
        orders = orders.filter(broker_id=filters["broker"].pk)
    if filters.get("carrier"):
        orders = orders.filter(
            Q(proposed_carrier_id=filters["carrier"].pk)
            | Q(confirmed_carrier_id=filters["carrier"].pk)
        )
    if filters.get("status"):
        orders = orders.filter(status_id=filters["status"].pk)
    if filters.get("closure_status"):
        orders = orders.filter(closure_status=filters["closure_status"])
    if filters.get("cargo_type"):
        orders = orders.filter(cargo_type_id=filters["cargo_type"].pk)
    if filters.get("financial_status"):
        orders = orders.filter(financial_transactions__status=filters["financial_status"])
    return orders.distinct()


def order_rows(filters, report_type, *, user=None):
    filters = dict(filters)
    if report_type == "orders-overdue":
        filters["overdue"] = "yes"
    orders = filtered_orders(filters, user=user)
    if filters.get("overdue"):
        threshold = timezone.now() - timedelta(days=settings.ORDER_OVERDUE_DAYS)
        overdue_orders = orders.exclude(
            status__code__in=("entregada", "cancelada")
        ).filter(updated_at__lte=threshold)
        if filters["overdue"] == "yes":
            orders = orders.filter(pk__in=overdue_orders.values("pk"))
        elif filters["overdue"] == "no":
            orders = orders.exclude(pk__in=overdue_orders.values("pk"))

    group_by = filters.get("group_by")
    group_expressions = {
        "status": F("status__name"),
        "customer": F("customer__legal_name"),
        "carrier": Coalesce(
            "confirmed_carrier__legal_name",
            "proposed_carrier__legal_name",
            Value("Sin transportista"),
            output_field=CharField(),
        ),
        "broker": F("broker__username"),
    }
    if group_by in group_expressions:
        orders = orders.annotate(report_group_label=group_expressions[group_by])
        return orders.order_by("report_group_label", "-created_at")
    return orders.order_by("-created_at")


def transaction_rows(filters, income, *, user=None):
    from apps.finance.models import FinancialTransaction

    movement_codes = ("cobro-cliente",) if income else (
        "pago-transportista", "gasto-transporte", "otro-gasto"
    )
    transactions = FinancialTransaction.objects.select_related(
        "order",
        "order__customer",
        "order__broker",
        "movement_type",
        "currency",
        "adjustment_of",
    ).filter(
        status=FinancialStatus.PENDING, movement_type__code__in=movement_codes
    )
    if user is not None:
        transactions = transactions.filter(
            order_id__in=scope_orders(Order.objects.all(), user).values("pk")
        )
    values = _date_filters(filters, "transaction_date")
    if values:
        transactions = transactions.filter(**values)
    if filters.get("customer"):
        transactions = transactions.filter(order__customer_id=filters["customer"].pk)
    if filters.get("broker"):
        transactions = transactions.filter(order__broker_id=filters["broker"].pk)
    if filters.get("carrier"):
        transactions = transactions.filter(
            Q(order__proposed_carrier_id=filters["carrier"].pk)
            | Q(order__confirmed_carrier_id=filters["carrier"].pk)
        )
    if filters.get("cargo_type"):
        transactions = transactions.filter(order__cargo_type_id=filters["cargo_type"].pk)
    if filters.get("status"):
        transactions = transactions.filter(order__status_id=filters["status"].pk)
    if filters.get("financial_status"):
        transactions = transactions.filter(status=filters["financial_status"])
    return transactions.order_by("-transaction_date", "-created_at")


def commission_rows(filters, *, user=None):
    from apps.finance.models import Commission

    commissions = Commission.objects.select_related("order", "broker").filter(
        status__in=(
            CommissionStatus.CALCULATED,
            CommissionStatus.AUTHORIZED,
            CommissionStatus.PAID,
        )
    )
    if user is not None:
        commissions = commissions.filter(
            order_id__in=scope_orders(Order.objects.all(), user).values("pk")
        )
    values = _date_filters(filters, "calculated_at__date")
    if values:
        commissions = commissions.filter(**values)
    if filters.get("broker"):
        commissions = commissions.filter(broker_id=filters["broker"].pk)
    if filters.get("customer"):
        commissions = commissions.filter(order__customer_id=filters["customer"].pk)
    if filters.get("carrier"):
        commissions = commissions.filter(
            Q(order__proposed_carrier_id=filters["carrier"].pk)
            | Q(order__confirmed_carrier_id=filters["carrier"].pk)
        )
    if filters.get("cargo_type"):
        commissions = commissions.filter(order__cargo_type_id=filters["cargo_type"].pk)
    if filters.get("status"):
        commissions = commissions.filter(order__status_id=filters["status"].pk)
    if filters.get("commission_status"):
        commissions = commissions.filter(status=filters["commission_status"])
    return commissions.prefetch_related("debt_applications").order_by("-calculated_at")


def commission_summary_rows(filters, *, user=None):
    from apps.finance.models import Commission

    commissions = Commission.objects.filter(
        status__in=(
            CommissionStatus.CALCULATED,
            CommissionStatus.AUTHORIZED,
            CommissionStatus.PAID,
        )
    )
    if user is not None:
        commissions = commissions.filter(
            order_id__in=scope_orders(Order.objects.all(), user).values("pk")
        )
    values = _date_filters(filters, "calculated_at__date")
    if values:
        commissions = commissions.filter(**values)
    if filters.get("customer"):
        commissions = commissions.filter(order__customer_id=filters["customer"].pk)
    if filters.get("carrier"):
        commissions = commissions.filter(
            Q(order__proposed_carrier_id=filters["carrier"].pk)
            | Q(order__confirmed_carrier_id=filters["carrier"].pk)
        )
    if filters.get("cargo_type"):
        commissions = commissions.filter(order__cargo_type_id=filters["cargo_type"].pk)
    if filters.get("status"):
        commissions = commissions.filter(order__status_id=filters["status"].pk)
    if filters.get("commission_status"):
        commissions = commissions.filter(status=filters["commission_status"])

    amount_field = DecimalField(max_digits=14, decimal_places=2)
    applied_debt = (
        CommissionDebtApplication.objects.filter(commission_id=OuterRef("pk"))
        .order_by()
        .values("commission_id")
        .annotate(total=Sum("amount_usd"))
        .values("total")[:1]
    )
    commissions = commissions.annotate(
        applied_debt_usd=Coalesce(
            Subquery(applied_debt, output_field=amount_field),
            Value(Decimal("0.00")),
            output_field=amount_field,
        )
    ).annotate(
        payable_amount_usd=Greatest(
            ExpressionWrapper(
                F("commission_amount_usd") - F("applied_debt_usd"),
                output_field=amount_field,
            ),
            Value(Decimal("0.00")),
            output_field=amount_field,
        )
    )
    return (
        commissions.values("broker_id", "broker__username")
        .annotate(
            order_count=Count("pk"),
            commission_total_usd=Sum("commission_amount_usd"),
            applied_debt_total_usd=Sum("applied_debt_usd"),
            payable_total_usd=Sum("payable_amount_usd"),
            calculated_count=Count("pk", filter=Q(status=CommissionStatus.CALCULATED)),
            authorized_count=Count("pk", filter=Q(status=CommissionStatus.AUTHORIZED)),
            paid_count=Count("pk", filter=Q(status=CommissionStatus.PAID)),
        )
        .order_by("broker__username")
    )


def financial_summary_rows(filters, *, user=None):
    amount_field = DecimalField(max_digits=14, decimal_places=2)
    order_filters = dict(filters)
    date_from = order_filters.pop("date_from", None)
    date_to = order_filters.pop("date_to", None)
    order_filters.pop("date_basis", None)
    order_filters.pop("financial_status", None)
    orders = filtered_orders(order_filters, user=user)

    transaction_period_filters = _date_filters(
        {"date_from": date_from, "date_to": date_to}, "transaction_date"
    )
    if transaction_period_filters or filters.get("financial_status"):
        matching_transactions = FinancialTransaction.objects.filter(order_id=OuterRef("pk"))
        if transaction_period_filters:
            matching_transactions = matching_transactions.filter(**transaction_period_filters)
        if filters.get("financial_status"):
            matching_transactions = matching_transactions.filter(
                status=filters["financial_status"]
            )
        orders = orders.annotate(
            has_matching_movement=Exists(matching_transactions)
        ).filter(has_matching_movement=True)

    confirmed_transactions = FinancialTransaction.objects.filter(
        order_id=OuterRef("pk"), status=FinancialStatus.CONFIRMED
    )
    if transaction_period_filters:
        confirmed_transactions = confirmed_transactions.filter(**transaction_period_filters)
    all_confirmed_transactions = FinancialTransaction.objects.filter(
        order_id=OuterRef("pk"), status=FinancialStatus.CONFIRMED
    )
    effective_type = Coalesce(
        "adjustment_of__adjustment_of__movement_type__code",
        "adjustment_of__movement_type__code",
        "movement_type__code",
        output_field=CharField(),
    )
    signed_amount = Case(
        When(adjustment_of__isnull=True, then=F("base_amount_usd")),
        When(adjustment_of__adjustment_of__isnull=True, then=-F("base_amount_usd")),
        default=F("base_amount_usd"),
        output_field=amount_field,
    )

    def total_subquery(source, *, income):
        movements = source.annotate(
            effective_movement_code=effective_type,
            effective_amount_usd=signed_amount,
        )
        if income:
            movements = movements.filter(effective_movement_code="cobro-cliente")
        else:
            movements = movements.exclude(effective_movement_code="cobro-cliente")
        return (
            movements.order_by()
            .values("order_id")
            .annotate(total=Sum("effective_amount_usd"))
            .values("total")[:1]
        )

    def commercial_adjustment_subquery(target):
        return (
            CommercialAdjustment.objects.filter(
                order_id=OuterRef("pk"),
                target=target,
                status=CommercialAdjustmentStatus.APPROVED,
            )
            .order_by()
            .values("order_id")
            .annotate(total=Sum("amount_usd"))
            .values("total")[:1]
        )

    zero = Value(Decimal("0.00"), output_field=amount_field)
    current_customer_received = Coalesce(
        Subquery(
            total_subquery(all_confirmed_transactions, income=True),
            output_field=amount_field,
        ),
        zero,
        output_field=amount_field,
    )
    current_carrier_paid = Coalesce(
        Subquery(
            all_confirmed_transactions.annotate(
                effective_movement_code=effective_type,
                effective_amount_usd=signed_amount,
            )
            .filter(effective_movement_code="pago-transportista")
            .order_by()
            .values("order_id")
            .annotate(total=Sum("effective_amount_usd"))
            .values("total")[:1],
            output_field=amount_field,
        ),
        zero,
        output_field=amount_field,
    )

    return orders.annotate(
        income_usd=Coalesce(
            Subquery(
                total_subquery(confirmed_transactions, income=True),
                output_field=amount_field,
            ),
            zero,
            output_field=amount_field,
        ),
        expenses_usd=Coalesce(
            Subquery(
                total_subquery(confirmed_transactions, income=False),
                output_field=amount_field,
            ),
            zero,
            output_field=amount_field,
        ),
        customer_adjustment_usd=Coalesce(
            Subquery(
                commercial_adjustment_subquery(CommercialAdjustmentTarget.CUSTOMER),
                output_field=amount_field,
            ),
            zero,
            output_field=amount_field,
        ),
        carrier_adjustment_usd=Coalesce(
            Subquery(
                commercial_adjustment_subquery(CommercialAdjustmentTarget.CARRIER),
                output_field=amount_field,
            ),
            zero,
            output_field=amount_field,
        ),
        customer_received_usd=current_customer_received,
        carrier_paid_usd=current_carrier_paid,
    ).annotate(
        profit_usd=F("income_usd") - F("expenses_usd"),
        customer_amount_due_usd=F("customer_rate") + F("customer_adjustment_usd"),
        customer_balance_usd=F("customer_rate")
        + F("customer_adjustment_usd")
        - F("customer_received_usd"),
        carrier_amount_due_usd=F("carrier_cost") + F("carrier_adjustment_usd"),
        carrier_balance_usd=F("carrier_cost")
        + F("carrier_adjustment_usd")
        - F("carrier_paid_usd"),
    ).order_by("-created_at")


def report_queryset(report_type, filters, *, user=None):
    if report_type in {"pending-collections", "pending-payments"}:
        return transaction_rows(
            filters, report_type == "pending-collections", user=user
        )
    if report_type == "commissions":
        if filters.get("broker"):
            return commission_rows(filters, user=user)
        return commission_summary_rows(filters, user=user)
    if report_type == "financial-summary":
        return financial_summary_rows(filters, user=user)
    return order_rows(filters, report_type, user=user)


def dashboard_metrics(filters, *, user=None):
    orders = filtered_orders(filters, user=user)
    active = orders.exclude(status__code="cancelada").exclude(
        closure_status="closed"
    ).count()
    overdue = order_rows(filters, "orders-overdue", user=user).count()
    financial = financial_summary_rows(filters, user=user)
    financial_totals = financial.aggregate(
        income=Sum("income_usd"), expenses=Sum("expenses_usd")
    )
    income = financial_totals["income"] or Decimal("0")
    expenses = financial_totals["expenses"] or Decimal("0")
    pending_collections = transaction_rows(filters, True, user=user).count()
    pending_payments = transaction_rows(filters, False, user=user).count()
    commissions = commission_rows(filters, user=user).filter(
        status__in=(CommissionStatus.CALCULATED, CommissionStatus.AUTHORIZED)
    )
    return {
        "active_orders": active,
        "overdue_orders": overdue,
        "pending_collections": pending_collections,
        "pending_payments": pending_payments,
        "income_usd": income,
        "expenses_usd": expenses,
        "profit_usd": income - expenses,
        "pending_commissions": commissions.count(),
        "pending_debts": commissions.filter(
            order__broker__broker_debts__status="open"
        ).distinct().count(),
        "financial_orders": financial.count(),
    }


def csv_response(report_type, rows, actor, filters):
    output = StringIO()
    writer = csv.writer(output)
    if report_type.startswith("pending-"):
        writer.writerow(
            (
                "Orden",
                "Cliente",
                "Broker",
                "Movimiento",
                "Monto",
                "Moneda",
                "Fecha",
                "Ajuste de movimiento",
            )
        )
        for row in rows[:1000]:
            writer.writerow(
                (
                    row.order.number,
                    row.order.customer.legal_name,
                    row.order.broker,
                    row.movement_type.name,
                    row.amount,
                    row.currency.code.upper(),
                    row.transaction_date,
                    row.adjustment_of_id or "",
                )
            )
    elif report_type == "commissions" and not filters.get("broker"):
        writer.writerow(
            (
                "Broker",
                "Órdenes",
                "Comisión calculada USD",
                "Deuda aplicada USD",
                "Pagable USD",
                "Calculadas",
                "Autorizadas",
                "Pagadas",
            )
        )
        for row in rows[:1000]:
            writer.writerow(
                (
                    row["broker__username"],
                    row["order_count"],
                    row["commission_total_usd"],
                    row["applied_debt_total_usd"],
                    row["payable_total_usd"],
                    row["calculated_count"],
                    row["authorized_count"],
                    row["paid_count"],
                )
            )
    elif report_type == "commissions":
        writer.writerow(("Orden", "Broker", "Comisión USD", "Estado", "Fecha"))
        for row in rows[:1000]:
            writer.writerow(
                (
                    row.order.number,
                    row.broker,
                    row.payable_amount_usd,
                    row.get_status_display(),
                    row.calculated_at.date(),
                )
            )
    elif report_type == "financial-summary":
        writer.writerow(
            (
                "Orden",
                "Cliente",
                "Ingresos del período USD",
                "Costos y gastos del período USD",
                "Resultado del período USD",
                "Exigible cliente USD",
                "Cobrado neto USD",
                "Saldo cliente USD",
                "Exigible transportista USD",
                "Pagado neto USD",
                "Saldo transportista USD",
            )
        )
        for row in rows[:1000]:
            writer.writerow(
                (
                    row.number,
                    row.customer.legal_name,
                    row.income_usd,
                    row.expenses_usd,
                    row.profit_usd,
                    row.customer_amount_due_usd,
                    row.customer_received_usd,
                    row.customer_balance_usd,
                    row.carrier_amount_due_usd,
                    row.carrier_paid_usd,
                    row.carrier_balance_usd,
                )
            )
    else:
        writer.writerow(
            (
                "Orden",
                "Cliente",
                "Broker",
                "Transportista",
                "Estado",
                "Estado de cierre",
                "Tipo de carga",
                "Creada",
                "Entrega",
            )
        )
        for row in rows[:1000]:
            carrier = row.confirmed_carrier or row.proposed_carrier
            writer.writerow(
                (
                    row.number,
                    row.customer.legal_name,
                    row.broker,
                    carrier,
                    row.status.name,
                    row.get_closure_status_display(),
                    row.cargo_type.name,
                    row.created_at.date(),
                    row.delivery_date,
                )
            )
    AuditEvent.objects.create(
        actor=actor,
        action="export_report",
        entity_type="report",
        entity_id=report_type,
        metadata={"filters": audit_filter_metadata(filters)},
    )
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = f'attachment; filename="cargotrack-{report_type}.csv"'
    return response

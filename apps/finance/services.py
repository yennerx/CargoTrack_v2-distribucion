from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.orders.models import Order

from .models import (
    BrokerDebt,
    CommercialAdjustment,
    CommercialAdjustmentStatus,
    CommercialAdjustmentTarget,
    Commission,
    CommissionDebtApplication,
    CommissionRule,
    CommissionStatus,
    DebtStatus,
    FinancialReview,
    FinancialStatus,
    FinancialTransaction,
    ReviewStatus,
)

MANAGER_GROUPS = {"Gerente administrativo", "Gerente general"}


def is_manager(user):
    return user.is_superuser or user.groups.filter(name__in=MANAGER_GROUPS).exists()


def is_general_manager(user):
    return user.is_superuser or user.groups.filter(name="Gerente general").exists()


def is_dispatcher(user):
    return user.is_superuser or user.groups.filter(name="Dispatcher").exists()


def is_administrative_manager(user):
    return user.is_superuser or user.groups.filter(name="Gerente administrativo").exists()


def prepare_entry(entry):
    entry.base_amount_usd = (entry.amount * entry.exchange_rate_to_usd).quantize(Decimal("0.01"))
    return entry


def create_transaction(*, form, order, actor):
    with transaction.atomic():
        transaction_entry = form.save(commit=False)
        transaction_entry.order = order
        transaction_entry.created_by = actor
        prepare_entry(transaction_entry)
        transaction_entry.full_clean()
        transaction_entry.save()
        AuditEvent.objects.create(
            actor=actor,
            order=order,
            action="create_financial_transaction",
            entity_type="financial_transaction",
            entity_id=str(transaction_entry.pk),
            metadata={
                "movement_type": transaction_entry.movement_type.code,
                "status": transaction_entry.status,
            },
        )
    return transaction_entry


def confirm_transaction(*, transaction_entry, actor):
    if not actor.is_superuser and not actor.groups.filter(name="Dispatcher").exists():
        raise ValidationError("Solo el Dispatcher puede confirmar cobros y pagos.")
    if transaction_entry.status != FinancialStatus.PENDING:
        raise ValidationError("Solo se pueden confirmar movimientos pendientes.")
    transaction_entry.status = FinancialStatus.CONFIRMED
    transaction_entry.confirmed_by = actor
    transaction_entry.confirmed_at = timezone.now()
    transaction_entry.save(update_fields=("status", "confirmed_by", "confirmed_at", "updated_at"))
    AuditEvent.objects.create(
        actor=actor,
        order=transaction_entry.order,
        action="confirm_financial_transaction",
        entity_type="financial_transaction",
        entity_id=str(transaction_entry.pk),
        metadata={"status": transaction_entry.status},
    )
    return transaction_entry


def create_adjustment(*, original, form, actor):
    if original.status != FinancialStatus.CONFIRMED:
        raise ValidationError("Solo se puede ajustar un movimiento confirmado.")
    with transaction.atomic():
        adjustment = form.save(commit=False)
        adjustment.order = original.order
        adjustment.movement_type = original.movement_type
        adjustment.cost_type = original.cost_type
        adjustment.created_by = actor
        adjustment.adjustment_of = original
        adjustment.description = (
            f"Ajuste de movimiento {original.pk}: {adjustment.description}"
        ).strip()
        prepare_entry(adjustment)
        adjustment.full_clean()
        adjustment.save()
        AuditEvent.objects.create(
            actor=actor,
            order=original.order,
            action="create_financial_adjustment",
            entity_type="financial_transaction",
            entity_id=str(adjustment.pk),
            metadata={"adjustment_of": original.pk},
        )
    return adjustment


def register_commercial_adjustment(
    *, order, actor, target, amount_usd, reason, reference=""
):
    if not is_dispatcher(actor):
        raise ValidationError("Solo el Dispatcher puede registrar ajustes comerciales.")
    with transaction.atomic():
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        adjustment = CommercialAdjustment(
            order=locked_order,
            target=target,
            amount_usd=amount_usd,
            reason=reason.strip(),
            reference=reference.strip(),
            requested_by=actor,
        )
        adjustment.full_clean()
        adjustment.save()
        AuditEvent.objects.create(
            actor=actor,
            order=locked_order,
            action="request_commercial_adjustment",
            entity_type="commercial_adjustment",
            entity_id=str(adjustment.pk),
            metadata={
                "target": adjustment.target,
            },
        )
    return adjustment


def review_commercial_adjustment(*, adjustment, actor, decision, observation=""):
    if not is_administrative_manager(actor):
        raise ValidationError("Solo la Gerencia administrativa puede revisar ajustes comerciales.")
    if decision not in {
        CommercialAdjustmentStatus.APPROVED,
        CommercialAdjustmentStatus.REJECTED,
    }:
        raise ValidationError("Seleccione aprobar o rechazar el ajuste.")
    if decision == CommercialAdjustmentStatus.REJECTED and not observation.strip():
        raise ValidationError("Indique el motivo del rechazo.")

    with transaction.atomic():
        locked_adjustment = CommercialAdjustment.objects.select_for_update().get(pk=adjustment.pk)
        if locked_adjustment.status != CommercialAdjustmentStatus.PENDING:
            raise ValidationError("Solo se pueden revisar ajustes pendientes.")
        locked_adjustment.status = decision
        locked_adjustment.reviewed_by = actor
        locked_adjustment.reviewed_at = timezone.now()
        locked_adjustment.review_observation = observation.strip()
        locked_adjustment.full_clean()
        locked_adjustment.save(
            update_fields=(
                "status",
                "reviewed_by",
                "reviewed_at",
                "review_observation",
                "updated_at",
            )
        )
        AuditEvent.objects.create(
            actor=actor,
            order=locked_adjustment.order,
            action=(
                "approve_commercial_adjustment"
                if decision == CommercialAdjustmentStatus.APPROVED
                else "reject_commercial_adjustment"
            ),
            entity_type="commercial_adjustment",
            entity_id=str(locked_adjustment.pk),
            metadata={
                "target": locked_adjustment.target,
                "status": locked_adjustment.status,
            },
        )
    return locked_adjustment


def confirmed_financial_totals(orders, *, date_from=None, date_to=None):
    entries = list(
        FinancialTransaction.objects.filter(order_id__in=orders)
        .values(
            "pk",
            "order_id",
            "status",
            "transaction_date",
            "base_amount_usd",
            "movement_type__code",
            "adjustment_of_id",
        )
    )
    entries_by_id = {entry["pk"]: entry for entry in entries}
    totals = {}

    for entry in entries:
        if entry["status"] != FinancialStatus.CONFIRMED:
            continue
        if date_from and entry["transaction_date"] < date_from:
            continue
        if date_to and entry["transaction_date"] > date_to:
            continue

        effect = Decimal("1")
        root = entry
        visited = set()
        while root["adjustment_of_id"]:
            parent_id = root["adjustment_of_id"]
            if parent_id in visited or parent_id not in entries_by_id:
                break
            visited.add(parent_id)
            effect *= Decimal("-1")
            root = entries_by_id[parent_id]
        amount = entry["base_amount_usd"] * effect
        movement_code = root["movement_type__code"]
        order_totals = totals.setdefault(
            entry["order_id"],
            {
                "income_usd": Decimal("0.00"),
                "expenses_usd": Decimal("0.00"),
                "customer_received_usd": Decimal("0.00"),
                "carrier_paid_usd": Decimal("0.00"),
            },
        )
        if movement_code == "cobro-cliente":
            order_totals["income_usd"] += amount
            order_totals["customer_received_usd"] += amount
        else:
            order_totals["expenses_usd"] += amount
            if movement_code == "pago-transportista":
                order_totals["carrier_paid_usd"] += amount

    return {
        order_id: {
            field: amount.quantize(Decimal("0.01")) for field, amount in values.items()
        }
        for order_id, values in totals.items()
    }


def order_financial_summary(order):
    movements = confirmed_financial_totals((order.pk,)).get(
        order.pk,
        {
            "income_usd": Decimal("0.00"),
            "expenses_usd": Decimal("0.00"),
            "customer_received_usd": Decimal("0.00"),
            "carrier_paid_usd": Decimal("0.00"),
        },
    )
    approved_adjustments = CommercialAdjustment.objects.filter(
        order=order, status=CommercialAdjustmentStatus.APPROVED
    )
    adjustment_totals = {
        row["target"]: row["total"] or Decimal("0.00")
        for row in approved_adjustments.values("target").annotate(total=Sum("amount_usd"))
    }
    customer_adjustment = adjustment_totals.get(
        CommercialAdjustmentTarget.CUSTOMER, Decimal("0.00")
    )
    carrier_adjustment = adjustment_totals.get(
        CommercialAdjustmentTarget.CARRIER, Decimal("0.00")
    )
    customer_amount_due = order.customer_rate + customer_adjustment
    carrier_amount_due = order.carrier_cost + carrier_adjustment
    customer_balance = customer_amount_due - movements["customer_received_usd"]
    carrier_balance = carrier_amount_due - movements["carrier_paid_usd"]
    pending = order.financial_transactions.filter(status=FinancialStatus.PENDING)
    pending_amount = pending.aggregate(total=Sum("base_amount_usd"))["total"] or Decimal("0.00")
    return {
        **movements,
        "profit_usd": movements["income_usd"] - movements["expenses_usd"],
        "customer_adjustment_usd": customer_adjustment,
        "customer_amount_due_usd": customer_amount_due,
        "customer_balance_usd": customer_balance,
        "customer_credit_usd": max(-customer_balance, Decimal("0.00")),
        "carrier_adjustment_usd": carrier_adjustment,
        "carrier_amount_due_usd": carrier_amount_due,
        "carrier_balance_usd": carrier_balance,
        "carrier_credit_usd": max(-carrier_balance, Decimal("0.00")),
        "pending_movements_count": pending.count(),
        "pending_movements_usd": pending_amount,
    }


def validate_financial_summary(*, order, actor, observation=""):
    if not actor.is_superuser and not actor.groups.filter(name="Gerente administrativo").exists():
        raise ValidationError("Solo la Gerencia administrativa puede validar el resumen.")
    review, _created = FinancialReview.objects.get_or_create(order=order)
    review.status = ReviewStatus.VALIDATED
    review.observation = observation.strip()
    review.reviewed_by = actor
    review.reviewed_at = timezone.now()
    review.save()
    AuditEvent.objects.create(
        actor=actor,
        order=order,
        action="validate_financial_summary",
        entity_type="financial_review",
        entity_id=str(review.pk),
        metadata={"status": review.status},
    )
    return review


def calculate_commission(*, order, actor, customer_unpaid_discount=Decimal("0")):
    if not is_manager(actor):
        raise ValidationError("Solo una gerencia puede calcular comisiones.")
    review = getattr(order, "financial_review", None)
    if not review or review.status != ReviewStatus.VALIDATED:
        raise ValidationError(
            "El resumen financiero debe estar validado antes de calcular la comisión."
        )
    if customer_unpaid_discount < 0:
        raise ValidationError("El descuento por falta de pago no puede ser negativo.")
    effective_date = order.delivery_date
    rule = (
        CommissionRule.objects.filter(
            broker=order.broker,
            is_active=True,
            valid_from__lte=effective_date,
        )
        .filter(models_q_valid_to(effective_date))
        .order_by("-valid_from", "-created_at")
        .first()
    )
    if not rule:
        raise ValidationError("No existe un porcentaje vigente para el broker.")
    summary = order_financial_summary(order)
    gross_profit = summary["profit_usd"]
    positive_profit = max(gross_profit, Decimal("0"))
    gross_commission = (
        positive_profit * rule.percentage / Decimal("100")
    ).quantize(Decimal("0.01"))
    commission_amount = max(gross_commission - customer_unpaid_discount, Decimal("0"))
    loss_amount = (
        max(-gross_profit, Decimal("0"))
        + max(customer_unpaid_discount - gross_commission, Decimal("0"))
    ).quantize(Decimal("0.01"))
    with transaction.atomic():
        commission, created = Commission.objects.get_or_create(
            order=order,
            defaults={
                "broker": order.broker,
                "rule": rule,
                "gross_profit_usd": gross_profit,
                "commission_rate": rule.percentage,
                "gross_commission_usd": gross_commission,
                "customer_unpaid_discount_usd": customer_unpaid_discount,
                "commission_amount_usd": commission_amount,
                "loss_amount_usd": loss_amount,
                "calculated_by": actor,
            },
        )
        if not created:
            if commission.status != CommissionStatus.CALCULATED:
                raise ValidationError("Solo se puede recalcular una comisión no autorizada.")
            commission.broker = order.broker
            commission.rule = rule
            commission.gross_profit_usd = gross_profit
            commission.commission_rate = rule.percentage
            commission.gross_commission_usd = gross_commission
            commission.customer_unpaid_discount_usd = customer_unpaid_discount
            commission.commission_amount_usd = commission_amount
            commission.loss_amount_usd = loss_amount
            commission.calculated_by = actor
            commission.save()
        AuditEvent.objects.create(
            actor=actor,
            order=order,
            action="calculate_commission",
            entity_type="commission",
            entity_id=str(commission.pk),
            metadata={"status": commission.status},
        )
    return commission


def models_q_valid_to(effective_date):
    from django.db.models import Q

    return Q(valid_to__isnull=True) | Q(valid_to__gte=effective_date)


def record_loss_agreement(
    *, commission, actor, company_covered_loss, agreed_broker_debt,
    responsibility_percentage, loss_report, negotiation_agreement
):
    if not is_manager(actor):
        raise ValidationError("Solo una gerencia puede registrar la negociación de una pérdida.")
    if commission.status != CommissionStatus.CALCULATED:
        raise ValidationError("La pérdida solo puede negociarse antes de autorizar la comisión.")
    if commission.loss_amount_usd <= 0:
        raise ValidationError("La comisión no tiene una pérdida que negociar.")
    if not loss_report.strip() or not negotiation_agreement.strip():
        raise ValidationError("El informe y el acuerdo de negociación son obligatorios.")
    total = company_covered_loss + agreed_broker_debt
    if total != commission.loss_amount_usd:
        raise ValidationError("La cobertura y la deuda deben distribuir toda la pérdida calculada.")
    with transaction.atomic():
        commission.company_covered_loss_usd = company_covered_loss
        commission.agreed_broker_debt_usd = agreed_broker_debt
        commission.loss_report = loss_report.strip()
        commission.negotiation_agreement = negotiation_agreement.strip()
        commission.save()
        debt = None
        if agreed_broker_debt > 0:
            debt = BrokerDebt.objects.create(
                broker=commission.broker,
                origin_commission=commission,
                loss_report=commission.loss_report,
                negotiation_agreement=commission.negotiation_agreement,
                loss_amount_usd=commission.loss_amount_usd,
                company_covered_loss_usd=company_covered_loss,
                agreed_amount_usd=agreed_broker_debt,
                balance_usd=agreed_broker_debt,
                responsibility_percentage=responsibility_percentage,
                approved_by=actor,
            )
        AuditEvent.objects.create(
            actor=actor,
            order=commission.order,
            action="record_commission_loss_agreement",
            entity_type="commission",
            entity_id=str(commission.pk),
            metadata={"broker_debt_created": debt is not None},
        )
    return debt


def apply_debt_to_commission(*, debt, commission, amount, actor):
    if not is_manager(actor):
        raise ValidationError("Solo una gerencia puede aplicar una deuda a una comisión.")
    if debt.status != DebtStatus.OPEN or debt.broker_id != commission.broker_id:
        raise ValidationError("La deuda no está disponible para este broker.")
    if commission.status not in {CommissionStatus.CALCULATED, CommissionStatus.AUTHORIZED}:
        raise ValidationError("Solo se puede descontar una comisión no pagada.")
    if amount <= 0:
        raise ValidationError("El descuento debe ser mayor que cero.")
    if amount > debt.balance_usd:
        raise ValidationError("El descuento supera el saldo de la deuda.")
    if amount > commission.payable_amount_usd:
        raise ValidationError("El descuento supera la comisión disponible.")
    with transaction.atomic():
        application = CommissionDebtApplication.objects.create(
            debt=debt, commission=commission, amount_usd=amount, applied_by=actor
        )
        debt.balance_usd -= amount
        if debt.balance_usd == 0:
            debt.status = DebtStatus.SETTLED
        debt.save(update_fields=("balance_usd", "status", "updated_at"))
        AuditEvent.objects.create(
            actor=actor,
            order=commission.order,
            action="apply_broker_debt",
            entity_type="commission_debt_application",
            entity_id=str(application.pk),
            metadata={
                "debt_id": debt.pk,
                "commission_id": commission.pk,
            },
        )
    return application


def authorize_commission(*, commission, actor):
    if not is_general_manager(actor):
        raise ValidationError("Solo el Gerente General puede autorizar comisiones.")
    if commission.status != CommissionStatus.CALCULATED:
        raise ValidationError("Solo se pueden autorizar comisiones calculadas.")
    if commission.loss_amount_usd > 0 and (
        not commission.loss_report
        or commission.company_covered_loss_usd + commission.agreed_broker_debt_usd
        != commission.loss_amount_usd
    ):
        raise ValidationError("La pérdida debe tener informe y distribución negociada.")
    commission.status = CommissionStatus.AUTHORIZED
    commission.authorized_by = actor
    commission.authorized_at = timezone.now()
    commission.save(update_fields=("status", "authorized_by", "authorized_at", "updated_at"))
    AuditEvent.objects.create(
        actor=actor,
        order=commission.order,
        action="authorize_commission",
        entity_type="commission",
        entity_id=str(commission.pk),
        metadata={"status": commission.status},
    )
    return commission


def record_commission_payment(*, commission, actor, payment_method, payment_reference=""):
    if not is_general_manager(actor):
        raise ValidationError("Solo el Gerente General puede registrar pagos de comisiones.")
    if commission.status != CommissionStatus.AUTHORIZED:
        raise ValidationError("Solo se puede pagar una comisión autorizada.")
    if not payment_method.strip():
        raise ValidationError("Indique el método de pago externo.")
    commission.status = CommissionStatus.PAID
    commission.paid_by = actor
    commission.paid_at = timezone.now()
    commission.payment_method = payment_method.strip()
    commission.payment_reference = payment_reference.strip()
    commission.save(
        update_fields=(
            "status", "paid_by", "paid_at", "payment_method", "payment_reference", "updated_at"
        )
    )
    AuditEvent.objects.create(
        actor=actor,
        order=commission.order,
        action="record_commission_payment",
        entity_type="commission",
        entity_id=str(commission.pk),
        metadata={"status": commission.status},
    )
    return commission

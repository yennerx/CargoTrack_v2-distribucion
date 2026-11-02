from datetime import timedelta

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.carriers.models import Carrier
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.core.access_scope import is_broker

from .models import (
    Order,
    OrderClosureStatus,
    OrderNumberSequence,
    OrderStatusHistory,
)

ALLOWED_TRANSITIONS = {
    "solicitud-recibida": {"en-negociacion", "cancelada"},
    "en-negociacion": {"pendiente-documentacion", "cancelada"},
    "pendiente-documentacion": {"validada", "en-negociacion", "cancelada"},
    "validada": {"asignada", "pendiente-documentacion", "cancelada"},
    "asignada": {"en-recogida", "validada", "cancelada"},
    "en-recogida": {"en-transito", "cancelada"},
    "en-transito": {"entregada", "cancelada"},
    "entregada": set(),
    "cancelada": set(),
}

CLOSURE_STATUS_BY_CODE = {
    "pendiente-cierre": OrderClosureStatus.PENDING,
    "cerrada": OrderClosureStatus.CLOSED,
    "reabierta": OrderClosureStatus.REOPENED,
}
CANCELLATION_STATUS_CODE = "cancelada"


def allowed_transition_codes(order):
    if order.closure_status == OrderClosureStatus.CLOSED:
        return {"reabierta"}
    if order.closure_status == OrderClosureStatus.PENDING:
        return {"cerrada"}
    if order.closure_status == OrderClosureStatus.REOPENED:
        return {"pendiente-cierre"}
    if order.status.code == "entregada":
        return {"pendiente-cierre"}
    return ALLOWED_TRANSITIONS.get(order.status.code, set())


def closing_validation_errors(order):
    from apps.documents.services import order_closing_document_errors
    from apps.finance.models import CommissionStatus, FinancialStatus, ReviewStatus

    errors = order_closing_document_errors(order)
    review = getattr(order, "financial_review", None)
    if not review or review.status != ReviewStatus.VALIDATED:
        errors.append("El resumen financiero debe estar validado.")
    transactions = order.financial_transactions.exclude(status=FinancialStatus.VOIDED)
    if transactions.filter(status=FinancialStatus.PENDING).exists():
        errors.append("Existen movimientos financieros pendientes de confirmación.")
    commission = getattr(order, "commission", None)
    if not commission or commission.status not in {
        CommissionStatus.CALCULATED,
        CommissionStatus.AUTHORIZED,
        CommissionStatus.PAID,
    }:
        errors.append("La comisión o cargo debe estar calculado.")
    elif commission.loss_amount_usd > 0 and (
        not commission.loss_report
        or commission.company_covered_loss_usd + commission.agreed_broker_debt_usd
        != commission.loss_amount_usd
        or (
            commission.agreed_broker_debt_usd > 0
            and not hasattr(commission, "broker_debt")
        )
    ):
        errors.append("La pérdida debe estar negociada y documentada.")
    if order.incidents.filter(
        priority__code="critica", status__in=("open", "in_progress", "reopened")
    ).exists():
        errors.append("Existen incidencias críticas abiertas.")
    return errors


def generate_order_number():
    year = timezone.localdate().year
    with transaction.atomic():
        sequence, _ = OrderNumberSequence.objects.select_for_update().get_or_create(year=year)
        sequence.last_number += 1
        sequence.save(update_fields=("last_number",))
    return f"ORD-{year}-{sequence.last_number:06d}"


def initial_order_status():
    return CatalogEntry.objects.get(
        catalog_type=CatalogType.ORDER_STATUS,
        code="solicitud-recibida",
        is_active=True,
    )


def create_order(*, form, actor):
    order = form.save(commit=False)
    order.number = generate_order_number()
    order.status = initial_order_status()
    order.created_by = actor
    order.broker = actor if is_broker(actor) else form.cleaned_data["broker"]
    order.save()
    OrderStatusHistory.objects.create(order=order, status=order.status, changed_by=actor)
    return order


def transition_order(*, order, target_status, actor, observation=""):
    roles = set(actor.groups.values_list("name", flat=True))
    is_administrator = actor.is_superuser or "Administrador" in roles
    is_dispatcher = actor.is_superuser or "Dispatcher" in roles
    if target_status.code == "reabierta" and not (is_administrator or is_dispatcher):
        raise ValidationError("Solo el Dispatcher o el Administrador pueden reabrir una orden.")
    if target_status.code in {"pendiente-cierre", "cerrada"} and not (
        is_administrator or is_dispatcher
    ):
        raise ValidationError("Solo el Dispatcher o el Administrador pueden cerrar una orden.")
    if target_status.code in {
        CANCELLATION_STATUS_CODE,
        "reabierta",
    } and not observation.strip():
        raise ValidationError("La observación es obligatoria para cancelar o reabrir una orden.")
    with transaction.atomic():
        locked_order = (
            Order.objects.select_for_update()
            .select_related("status")
            .get(pk=order.pk)
        )
        confirmed_carrier = None
        if target_status.code == "asignada" and locked_order.confirmed_carrier_id:
            confirmed_carrier = Carrier.objects.select_for_update().get(
                pk=locked_order.confirmed_carrier_id
            )
        if target_status.code == "asignada" and (
            not locked_order.confirmed_carrier_id
            or confirmed_carrier.pk != locked_order.proposed_carrier_id
            or not locked_order.confirmed_by_id
            or not confirmed_carrier.is_active
            or not confirmed_carrier.is_validated
        ):
            raise ValidationError(
                "El Dispatcher debe confirmar el transportista propuesto, activo y validado antes "
                "de asignar la orden."
            )
        if target_status.code not in allowed_transition_codes(locked_order):
            raise ValidationError("La transición de estado solicitada no está permitida.")
        if target_status.code == "cerrada":
            closing_errors = closing_validation_errors(locked_order)
            if closing_errors:
                raise ValidationError(" ".join(closing_errors))
        last_history = locked_order.status_history.select_related("status").first()
        previous_status = last_history.status if last_history else None
        if target_status.code in CLOSURE_STATUS_BY_CODE:
            locked_order.closure_status = CLOSURE_STATUS_BY_CODE[target_status.code]
            update_fields = ("closure_status", "updated_at")
        else:
            locked_order.status = target_status
            update_fields = ("status", "updated_at")
        locked_order.save(update_fields=update_fields)
        OrderStatusHistory.objects.create(
            order=locked_order,
            previous_status=previous_status,
            status=target_status,
            changed_by=actor,
            observation=observation,
        )
    return locked_order


def order_is_overdue(order, *, today=None):
    today = today or timezone.localdate()
    last_update = order.updated_at.astimezone(timezone.get_current_timezone()).date()
    return (
        order.status.code not in {"entregada", "cancelada"}
        and today - last_update >= timedelta(days=settings.ORDER_OVERDUE_DAYS)
    )

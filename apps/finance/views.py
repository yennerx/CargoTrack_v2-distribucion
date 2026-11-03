from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from apps.audit.models import AuditEvent
from apps.core.access_scope import has_global_data_access, scope_orders
from apps.orders.models import Order

from .forms import (
    CommercialAdjustmentForm,
    CommercialAdjustmentReviewForm,
    CommissionCalculationForm,
    CommissionPaymentForm,
    CommissionRuleForm,
    DebtApplicationForm,
    FinancialAdjustmentForm,
    FinancialTransactionForm,
    LossAgreementForm,
)
from .models import (
    BrokerDebt,
    CommercialAdjustment,
    Commission,
    CommissionRule,
    FinancialTransaction,
)
from .services import (
    apply_debt_to_commission,
    authorize_commission,
    calculate_commission,
    confirm_transaction,
    create_adjustment,
    create_transaction,
    is_administrative_manager,
    is_dispatcher,
    order_financial_summary,
    record_commission_payment,
    record_loss_agreement,
    register_commercial_adjustment,
    review_commercial_adjustment,
    validate_financial_summary,
)


def require_permission(request, permission):
    if not request.user.has_perm(permission):
        raise PermissionDenied


def visible_order_ids(user):
    return scope_orders(Order.objects.all(), user).values("pk")


def visible_transactions(user):
    return FinancialTransaction.objects.filter(order_id__in=visible_order_ids(user))


@login_required
@require_GET
def finance_list(request):
    require_permission(request, "finance.view_financialtransaction")
    entries = FinancialTransaction.objects.select_related(
        "order", "movement_type", "currency", "adjustment_of"
    ).filter(order_id__in=visible_order_ids(request.user))
    return render(request, "finance/finance_list.html", {"transactions": entries[:100]})


@login_required
@require_GET
def order_finance(request, order_pk):
    require_permission(request, "finance.view_financialtransaction")
    order = get_object_or_404(
        scope_orders(Order.objects.all(), request.user), pk=order_pk
    )
    return render(
        request,
        "finance/order_finance.html",
        order_finance_context(order, user=request.user),
    )


def order_finance_context(order, *, user, commercial_form=None):
    return {
        "order": order,
        "transactions": order.financial_transactions.select_related(
            "movement_type", "cost_type", "currency", "created_by", "adjustment_of"
        ),
        "summary": order_financial_summary(order),
        "review": getattr(order, "financial_review", None),
        "commission": getattr(order, "commission", None),
        "commercial_adjustments": order.commercial_adjustments.select_related(
            "requested_by", "reviewed_by"
        ),
        "commercial_form": commercial_form or CommercialAdjustmentForm(),
        "can_register_commercial_adjustment": is_dispatcher(user),
        "can_review_commercial_adjustment": is_administrative_manager(user),
    }


@login_required
def transaction_create(request, order_pk):
    require_permission(request, "finance.add_financialtransaction")
    order = get_object_or_404(
        scope_orders(Order.objects.all(), request.user), pk=order_pk
    )
    if request.method == "POST":
        form = FinancialTransactionForm(request.POST)
        if form.is_valid():
            try:
                create_transaction(form=form, order=order, actor=request.user)
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "Movimiento financiero registrado.")
                return redirect("finance:order", order_pk=order.pk)
    else:
        form = FinancialTransactionForm()
    return render(request, "finance/transaction_form.html", {"form": form, "order": order})


@login_required
@require_POST
def transaction_confirm(request, pk):
    require_permission(request, "finance.change_financialtransaction")
    entry = get_object_or_404(visible_transactions(request.user), pk=pk)
    try:
        confirm_transaction(transaction_entry=entry, actor=request.user)
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "Movimiento confirmado.")
    return redirect("finance:order", order_pk=entry.order_id)


@login_required
@require_POST
def summary_validate(request, order_pk):
    require_permission(request, "finance.change_financialreview")
    order = get_object_or_404(
        scope_orders(Order.objects.all(), request.user), pk=order_pk
    )
    try:
        validate_financial_summary(
            order=order, actor=request.user, observation=request.POST.get("observation", "")
        )
    except ValidationError as error:
        messages.error(request, error.message)
    else:
        messages.success(request, "Resumen financiero validado.")
    return redirect("finance:order", order_pk=order.pk)


@login_required
def adjustment_create(request, pk):
    require_permission(request, "finance.add_financialtransaction")
    original = get_object_or_404(visible_transactions(request.user), pk=pk)
    if original.adjustment_of_id:
        messages.error(request, "Las correcciones deben apuntar al movimiento financiero original.")
        return redirect("finance:order", order_pk=original.order_id)
    if request.method == "POST":
        form = FinancialAdjustmentForm(request.POST, original=original)
        if form.is_valid():
            try:
                create_adjustment(original=original, form=form, actor=request.user)
            except ValidationError as error:
                messages.error(request, error.message)
            else:
                messages.success(request, "Ajuste compensatorio registrado.")
                return redirect("finance:order", order_pk=original.order_id)
    else:
        form = FinancialAdjustmentForm(original=original)
    return render(
        request,
        "finance/transaction_form.html",
        {"form": form, "order": original.order, "adjustment": original},
    )


@login_required
def commercial_adjustment_create(request, order_pk):
    require_permission(request, "finance.add_commercialadjustment")
    if not is_dispatcher(request.user):
        raise PermissionDenied
    order = get_object_or_404(
        scope_orders(Order.objects.all(), request.user), pk=order_pk
    )
    if request.method == "POST":
        form = CommercialAdjustmentForm(request.POST)
        if form.is_valid():
            try:
                register_commercial_adjustment(
                    order=order, actor=request.user, **form.cleaned_data
                )
            except ValidationError as error:
                form.add_error(None, error.message)
            else:
                messages.success(request, "Ajuste comercial enviado a aprobación.")
                return redirect("finance:order", order_pk=order.pk)
    else:
        form = CommercialAdjustmentForm()
    return render(
        request,
        "finance/commercial_adjustment_form.html",
        {"order": order, "form": form},
    )


@login_required
@require_POST
def commercial_adjustment_review(request, pk):
    require_permission(request, "finance.change_commercialadjustment")
    if not is_administrative_manager(request.user):
        raise PermissionDenied
    adjustment = get_object_or_404(
        CommercialAdjustment.objects.filter(order_id__in=visible_order_ids(request.user)),
        pk=pk,
    )
    form = CommercialAdjustmentReviewForm(request.POST)
    if form.is_valid():
        try:
            review_commercial_adjustment(
                adjustment=adjustment,
                actor=request.user,
                decision=request.POST.get("decision", ""),
                observation=form.cleaned_data["observation"],
            )
        except ValidationError as error:
            messages.error(request, error.message)
        else:
            messages.success(request, "Ajuste comercial revisado.")
    else:
        messages.error(request, "Indique una observación válida para la revisión.")
    return redirect("finance:order", order_pk=adjustment.order_id)


@login_required
@require_GET
def commission_list(request):
    require_permission(request, "finance.view_commission")
    commissions = Commission.objects.select_related("order", "broker").filter(
        order_id__in=visible_order_ids(request.user)
    )
    debts = BrokerDebt.objects.filter(
        status="open", origin_commission__order_id__in=visible_order_ids(request.user)
    ).select_related("broker")
    return render(
        request,
        "finance/commission_list.html",
        {"commissions": commissions, "debts": debts},
    )


@login_required
def commission_calculate(request, order_pk):
    require_permission(request, "finance.add_commission")
    order = get_object_or_404(
        scope_orders(Order.objects.all(), request.user), pk=order_pk
    )
    if request.method == "POST":
        form = CommissionCalculationForm(request.POST)
        if form.is_valid():
            try:
                commission = calculate_commission(
                    order=order,
                    actor=request.user,
                    customer_unpaid_discount=form.cleaned_data["customer_unpaid_discount"],
                )
            except ValidationError as error:
                form.add_error(None, str(error))
            else:
                messages.success(request, "Comisión calculada.")
                return redirect("finance:commission-detail", pk=commission.pk)
    else:
        form = CommissionCalculationForm()
    return render(request, "finance/commission_form.html", {"form": form, "order": order})


@login_required
@require_GET
def commission_detail(request, pk):
    require_permission(request, "finance.view_commission")
    commission = get_object_or_404(
        Commission.objects.filter(order_id__in=visible_order_ids(request.user)).select_related(
            "order", "broker", "rule", "authorized_by", "paid_by"
        ),
        pk=pk,
    )
    debts = BrokerDebt.objects.filter(
        broker=commission.broker,
        status="open",
        origin_commission__order_id__in=visible_order_ids(request.user),
    ).order_by("created_at")
    return render(
        request,
        "finance/commission_detail.html",
        {
            "commission": commission,
            "loss_form": LossAgreementForm(),
            "payment_form": CommissionPaymentForm(),
            "debt_form": DebtApplicationForm(),
            "debts": debts,
        },
    )


@login_required
@require_POST
def commission_loss(request, pk):
    require_permission(request, "finance.change_commission")
    commission = get_object_or_404(
        Commission.objects.filter(order_id__in=visible_order_ids(request.user)), pk=pk
    )
    form = LossAgreementForm(request.POST)
    if form.is_valid():
        try:
            record_loss_agreement(commission=commission, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Negociación de pérdida registrada.")
    else:
        messages.error(request, "Revise los datos de la negociación de pérdida.")
    return redirect("finance:commission-detail", pk=pk)


@login_required
@require_POST
def commission_authorize(request, pk):
    require_permission(request, "finance.change_commission")
    commission = get_object_or_404(
        Commission.objects.filter(order_id__in=visible_order_ids(request.user)), pk=pk
    )
    try:
        authorize_commission(commission=commission, actor=request.user)
    except ValidationError as error:
        messages.error(request, str(error))
    else:
        messages.success(request, "Comisión autorizada.")
    return redirect("finance:commission-detail", pk=pk)


@login_required
@require_POST
def commission_pay(request, pk):
    require_permission(request, "finance.change_commission")
    commission = get_object_or_404(
        Commission.objects.filter(order_id__in=visible_order_ids(request.user)), pk=pk
    )
    form = CommissionPaymentForm(request.POST)
    if form.is_valid():
        try:
            record_commission_payment(
                commission=commission, actor=request.user, **form.cleaned_data
            )
        except ValidationError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Pago de comisión registrado.")
    else:
        messages.error(request, "Indique el método de pago.")
    return redirect("finance:commission-detail", pk=pk)


@login_required
@require_POST
def debt_apply(request, pk):
    require_permission(request, "finance.change_commission")
    commission = get_object_or_404(
        Commission.objects.filter(order_id__in=visible_order_ids(request.user)), pk=pk
    )
    debt = get_object_or_404(
        BrokerDebt.objects.filter(
            origin_commission__order_id__in=visible_order_ids(request.user)
        ),
        pk=request.POST.get("debt_id"),
    )
    form = DebtApplicationForm(request.POST)
    if form.is_valid():
        try:
            apply_debt_to_commission(
                debt=debt,
                commission=commission,
                amount=form.cleaned_data["amount"],
                actor=request.user,
            )
        except ValidationError as error:
            messages.error(request, str(error))
        else:
            messages.success(request, "Descuento de deuda aplicado a la comisión.")
    else:
        messages.error(request, "Indique un monto válido para el descuento.")
    return redirect("finance:commission-detail", pk=pk)


@login_required
@require_GET
def commission_rules(request):
    require_permission(request, "finance.view_commissionrule")
    rules = CommissionRule.objects.select_related("broker", "created_by")
    if not has_global_data_access(request.user):
        rules = rules.filter(broker=request.user)
    return render(request, "finance/commission_rules.html", {"rules": rules})


@login_required
def commission_rule_form(request, pk=None):
    permission = "finance.change_commissionrule" if pk else "finance.add_commissionrule"
    require_permission(request, permission)
    rule_queryset = CommissionRule.objects.all()
    if not has_global_data_access(request.user):
        rule_queryset = rule_queryset.filter(broker=request.user)
    rule = get_object_or_404(rule_queryset, pk=pk) if pk else None
    if request.method == "POST":
        form = CommissionRuleForm(request.POST, instance=rule, actor=request.user)
        if form.is_valid():
            entry = form.save(commit=False)
            if not entry.created_by_id:
                entry.created_by = request.user
            try:
                entry.full_clean()
                entry.save()
            except ValidationError as error:
                form.add_error(None, str(error))
            else:
                AuditEvent.objects.create(
                    actor=request.user,
                    action="update_commission_rule" if rule else "create_commission_rule",
                    entity_type="commission_rule",
                    entity_id=str(entry.pk),
                    metadata={"broker_id": entry.broker_id},
                )
                messages.success(request, "Regla de comisión guardada.")
                return redirect("finance:commission-rules")
    else:
        form = CommissionRuleForm(instance=rule, actor=request.user)
    return render(request, "finance/commission_rule_form.html", {"form": form, "rule": rule})

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.urls import reverse

from apps.audit.models import AuditEvent
from apps.carriers.models import Carrier, CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.customers.models import Customer
from apps.orders.models import Order

from .forms import (
    CommercialAdjustmentForm,
    FinancialAdjustmentForm,
    FinancialTransactionForm,
)
from .models import (
    BrokerDebt,
    CommercialAdjustment,
    CommercialAdjustmentStatus,
    CommercialAdjustmentTarget,
    Commission,
    CommissionRule,
    FinancialReview,
    FinancialStatus,
    FinancialTransaction,
)
from .services import (
    apply_debt_to_commission,
    authorize_commission,
    calculate_commission,
    confirm_transaction,
    create_adjustment,
    order_financial_summary,
    record_commission_payment,
    record_loss_agreement,
    register_commercial_adjustment,
    review_commercial_adjustment,
    validate_financial_summary,
)


def grant(user, *codenames):
    user.user_permissions.add(
        *Permission.objects.filter(content_type__app_label="finance", codename__in=codenames)
    )


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(username="finance-user", password="test-pass-123")


@pytest.fixture
def order(user):
    customer = Customer.objects.create(nit="FIN001", legal_name="Cliente Finanzas", created_by=user)
    carrier = Carrier.objects.create(
        carrier_type=CarrierType.COMPANY,
        nit="FIN002",
        legal_name="Transportes Finanzas",
        primary_phone="5555",
        email="finance@example.com",
        created_by=user,
    )
    from apps.orders.models import Order

    return Order.objects.create(
        status=CatalogEntry.objects.get(code="solicitud-recibida"),
        customer=customer,
        proposed_carrier=carrier,
        broker=user,
        created_by=user,
        cargo_type=CatalogEntry.objects.filter(catalog_type=CatalogType.CARGO_TYPE).first(),
        equipment_type=CatalogEntry.objects.filter(catalog_type=CatalogType.EQUIPMENT_TYPE).first(),
        origin="Origen",
        destination="Destino",
        pickup_date=date.today(),
        delivery_date=date.today() + timedelta(days=2),
        customer_rate=Decimal("100.00"),
        carrier_cost=Decimal("80.00"),
        number="ORD-2026-000098",
    )


@pytest.mark.django_db
def test_broker_finance_views_include_only_visible_orders(client, user, order):
    grant(user, "view_financialtransaction")
    user.groups.add(Group.objects.get(name="Broker"))
    other_broker = get_user_model().objects.create_user(username="finance-other-broker")
    other_broker.groups.add(Group.objects.get(name="Broker"))
    from apps.orders.models import Order

    other_order = Order.objects.create(
        status=order.status,
        customer=order.customer,
        proposed_carrier=order.proposed_carrier,
        broker=other_broker,
        created_by=other_broker,
        cargo_type=order.cargo_type,
        equipment_type=order.equipment_type,
        origin=order.origin,
        destination=order.destination,
        pickup_date=order.pickup_date,
        delivery_date=order.delivery_date,
        customer_rate=order.customer_rate,
        carrier_cost=order.carrier_cost,
        number="ORD-FIN-OTHER-01",
    )
    movement_type = CatalogEntry.objects.get(code="cobro-cliente")
    currency = CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY)
    own_entry = FinancialTransaction.objects.create(
        order=order,
        movement_type=movement_type,
        currency=currency,
        amount=Decimal("50.00"),
        transaction_date=date.today(),
        created_by=user,
    )
    FinancialTransaction.objects.create(
        order=other_order,
        movement_type=movement_type,
        currency=currency,
        amount=Decimal("75.00"),
        transaction_date=date.today(),
        created_by=other_broker,
    )
    client.force_login(user)

    response = client.get(reverse("finance:list"))

    assert list(response.context["transactions"]) == [own_entry]
    assert client.get(
        reverse("finance:order", args=[other_order.pk])
    ).status_code == 404


def data(movement_code, amount="100.00", currency_code="usd", cost_type=None):
    values = {
        "movement_type": CatalogEntry.objects.get(
            catalog_type=CatalogType.FINANCIAL_MOVEMENT, code=movement_code
        ).pk,
        "currency": CatalogEntry.objects.get(
            catalog_type=CatalogType.CURRENCY, code=currency_code
        ).pk,
        "amount": amount,
        "exchange_rate_to_usd": "1",
        "transaction_date": date.today(),
        "reference": "REF-001",
        "description": "Movimiento de prueba",
    }
    if cost_type:
        data_type = CatalogEntry.objects.get(catalog_type=CatalogType.COST_TYPE, code=cost_type)
        values["cost_type"] = data_type.pk
    return values


@pytest.mark.django_db
def test_financial_form_uses_usd_by_default():
    form = FinancialTransactionForm()

    assert form.fields["currency"].initial.code == "usd"
    assert not form.fields["movement_type"].queryset.filter(code="impuesto").exists()


@pytest.mark.django_db
def test_financial_transaction_rejects_invalid_amount(order):
    form = FinancialTransactionForm(data=data("cobro-cliente", amount="0"))

    assert not form.is_valid()
    assert "amount" in form.errors


@pytest.mark.django_db
def test_summary_calculates_income_less_costs(order, user):
    income = FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="cobro-cliente"),
        currency=CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY),
        amount=Decimal("1000"),
        base_amount_usd=Decimal("1000"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="pago-transportista"),
        cost_type=CatalogEntry.objects.get(
            code="costo-transportista", catalog_type=CatalogType.COST_TYPE
        ),
        currency=income.currency,
        amount=Decimal("700"),
        base_amount_usd=Decimal("700"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )

    summary = order_financial_summary(order)

    assert summary["income_usd"] == Decimal("1000.00")
    assert summary["expenses_usd"] == Decimal("700.00")
    assert summary["profit_usd"] == Decimal("300.00")
    assert summary["customer_balance_usd"] == Decimal("-900.00")
    assert summary["customer_credit_usd"] == Decimal("900.00")
    assert summary["carrier_balance_usd"] == Decimal("-620.00")
    assert summary["carrier_credit_usd"] == Decimal("620.00")


@pytest.mark.django_db
def test_dispatcher_requests_adjustments_and_pending_requests_do_not_change_balances(
    order, user
):
    dispatcher = manager("Dispatcher", "adjustment-dispatcher")
    customer_request = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CUSTOMER,
        amount_usd=Decimal("25.00"),
        reason="Acuerdo adicional de entrega.",
        reference="AC-001",
    )
    carrier_request = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CARRIER,
        amount_usd=Decimal("-10.00"),
        reason="Descuento acordado por demora.",
    )

    summary = order_financial_summary(order)

    assert customer_request.status == CommercialAdjustmentStatus.PENDING
    assert carrier_request.status == CommercialAdjustmentStatus.PENDING
    assert summary["customer_amount_due_usd"] == Decimal("100.00")
    assert summary["carrier_amount_due_usd"] == Decimal("80.00")
    assert AuditEvent.objects.filter(action="request_commercial_adjustment").count() == 2


@pytest.mark.django_db
def test_dispatcher_can_submit_commercial_adjustment_from_order_finance_page(
    client, order, user
):
    user.groups.add(Group.objects.get(name="Dispatcher"))
    client.force_login(user)

    page = client.get(reverse("finance:order", args=[order.pk]))
    form_page = client.get(
        reverse("finance:commercial-adjustment-create", args=[order.pk])
    )
    invalid = client.post(
        reverse("finance:commercial-adjustment-create", args=[order.pk]),
        {
            "target": CommercialAdjustmentTarget.CARRIER,
            "amount_usd": "0",
            "reason": "Un ajuste nulo debe rechazarse.",
        },
    )
    assert invalid.status_code == 200
    assert "amount_usd" in invalid.context["form"].errors
    assert not CommercialAdjustment.objects.filter(order=order).exists()

    response = client.post(
        reverse("finance:commercial-adjustment-create", args=[order.pk]),
        {
            "target": CommercialAdjustmentTarget.CARRIER,
            "amount_usd": "15.00",
            "reason": "Acuerdo de costo adicional.",
            "reference": "AC-003",
        },
    )

    adjustment = CommercialAdjustment.objects.get(order=order)
    assert page.status_code == 200
    assert form_page.status_code == 200
    assert "Saldos económicos" in page.content.decode()
    assert response.status_code == 302
    assert adjustment.status == CommercialAdjustmentStatus.PENDING
    assert adjustment.requested_by == user


@pytest.mark.django_db
def test_administrative_manager_can_approve_commercial_adjustment_in_order_finance(
    client, order, user
):
    dispatcher = manager("Dispatcher", "approval-dispatcher")
    adjustment = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CUSTOMER,
        amount_usd=Decimal("12.50"),
        reason="Ajuste pactado para el servicio.",
    )
    administrative = manager("Gerente administrativo", "approval-admin")
    client.force_login(administrative)
    review_page = client.get(reverse("finance:order", args=[order.pk]))

    invalid_decision = client.post(
        reverse("finance:commercial-adjustment-review", args=[adjustment.pk]),
        {"decision": "unknown"},
    )
    adjustment.refresh_from_db()
    assert invalid_decision.status_code == 302
    assert adjustment.status == CommercialAdjustmentStatus.PENDING

    response = client.post(
        reverse("finance:commercial-adjustment-review", args=[adjustment.pk]),
        {"decision": CommercialAdjustmentStatus.APPROVED},
    )

    adjustment.refresh_from_db()
    assert response.status_code == 302
    assert review_page.status_code == 200
    assert "Aprobar" in review_page.content.decode()
    assert adjustment.status == CommercialAdjustmentStatus.APPROVED
    assert adjustment.reviewed_by == administrative
    assert order_financial_summary(order)["customer_amount_due_usd"] == Decimal("112.50")


@pytest.mark.django_db
def test_dispatcher_cannot_review_commercial_adjustment_through_view(client, order, user):
    dispatcher = manager("Dispatcher", "view-dispatcher")
    adjustment = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CUSTOMER,
        amount_usd=Decimal("5.00"),
        reason="Ajuste para probar autorización.",
    )
    client.force_login(dispatcher)

    response = client.post(
        reverse("finance:commercial-adjustment-review", args=[adjustment.pk]),
        {"decision": CommercialAdjustmentStatus.APPROVED},
    )

    assert response.status_code == 403
    assert CommercialAdjustment.objects.get(pk=adjustment.pk).status == "pending"


@pytest.mark.django_db
def test_administrator_technical_permissions_do_not_bypass_dispatcher_business_role(
    client, order
):
    administrator = manager("Administrador", "technical-admin-adjustment")
    client.force_login(administrator)

    response = client.get(reverse("finance:commercial-adjustment-create", args=[order.pk]))

    assert administrator.has_perm("finance.add_commercialadjustment")
    assert response.status_code == 403


@pytest.mark.django_db
def test_administrator_technical_permissions_do_not_bypass_approval_role(client, order):
    dispatcher = manager("Dispatcher", "technical-review-dispatcher")
    adjustment = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CUSTOMER,
        amount_usd=Decimal("5.00"),
        reason="Ajuste para validar autorización de revisión.",
    )
    administrator = manager("Administrador", "technical-review-admin")
    client.force_login(administrator)

    response = client.post(
        reverse("finance:commercial-adjustment-review", args=[adjustment.pk]),
        {"decision": CommercialAdjustmentStatus.APPROVED},
    )

    assert administrator.has_perm("finance.change_commercialadjustment")
    assert response.status_code == 403
    assert CommercialAdjustment.objects.get(pk=adjustment.pk).status == "pending"


@pytest.mark.django_db
def test_only_administrative_manager_approves_adjustments_and_rejections_are_audited(
    order, user
):
    dispatcher = manager("Dispatcher", "review-dispatcher")
    adjustment = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CUSTOMER,
        amount_usd=Decimal("-15.00"),
        reason="Descuento comercial autorizado por correo.",
    )
    with pytest.raises(ValidationError):
        review_commercial_adjustment(
            adjustment=adjustment,
            actor=dispatcher,
            decision=CommercialAdjustmentStatus.APPROVED,
        )

    administrative = manager("Gerente administrativo", "review-admin")
    with pytest.raises(ValidationError):
        review_commercial_adjustment(
            adjustment=adjustment,
            actor=administrative,
            decision=CommercialAdjustmentStatus.REJECTED,
        )
    reviewed = review_commercial_adjustment(
        adjustment=adjustment,
        actor=administrative,
        decision=CommercialAdjustmentStatus.REJECTED,
        observation="No se adjuntó respaldo del acuerdo.",
    )

    assert reviewed.status == CommercialAdjustmentStatus.REJECTED
    assert reviewed.reviewed_by == administrative
    assert order_financial_summary(order)["customer_amount_due_usd"] == Decimal("100.00")
    assert AuditEvent.objects.filter(action="reject_commercial_adjustment").exists()


@pytest.mark.django_db
def test_commission_manager_cannot_register_commercial_adjustment(order):
    administrative = manager("Gerente administrativo", "adjustment-admin-only-review")

    with pytest.raises(ValidationError):
        register_commercial_adjustment(
            order=order,
            actor=administrative,
            target=CommercialAdjustmentTarget.CUSTOMER,
            amount_usd=Decimal("20.00"),
            reason="Ajuste sin registro del Dispatcher.",
        )


@pytest.mark.django_db
def test_adjustment_form_accepts_positive_and_negative_commercial_amounts():
    for amount in ("25.00", "-25.00"):
        form = CommercialAdjustmentForm(
            data={
                "target": CommercialAdjustmentTarget.CUSTOMER,
                "amount_usd": amount,
                "reason": "Acuerdo comercial de prueba.",
                "reference": "AC-002",
            }
        )
        assert form.is_valid()
    zero_form = CommercialAdjustmentForm(
        data={
            "target": CommercialAdjustmentTarget.CARRIER,
            "amount_usd": "0",
            "reason": "Monto neutro no permitido.",
        }
    )
    assert not zero_form.is_valid()
    assert "amount_usd" in zero_form.errors


@pytest.mark.django_db
def test_balances_use_approved_adjustments_confirmed_partial_payments_and_compensations(
    order, user
):
    dispatcher = manager("Dispatcher", "balance-dispatcher")
    administrative = manager("Gerente administrativo", "balance-admin")
    customer_adjustment = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CUSTOMER,
        amount_usd=Decimal("20.00"),
        reason="Recargo pactado.",
    )
    carrier_adjustment = register_commercial_adjustment(
        order=order,
        actor=dispatcher,
        target=CommercialAdjustmentTarget.CARRIER,
        amount_usd=Decimal("-10.00"),
        reason="Descuento pactado.",
    )
    review_commercial_adjustment(
        adjustment=customer_adjustment,
        actor=administrative,
        decision=CommercialAdjustmentStatus.APPROVED,
    )
    review_commercial_adjustment(
        adjustment=carrier_adjustment,
        actor=administrative,
        decision=CommercialAdjustmentStatus.APPROVED,
    )
    currency = CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY)
    collection = FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="cobro-cliente"),
        currency=currency,
        amount=Decimal("50.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    FinancialTransaction.objects.create(
        order=order,
        movement_type=collection.movement_type,
        currency=currency,
        amount=Decimal("80.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    carrier_payment = FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="pago-transportista"),
        cost_type=CatalogEntry.objects.get(
            code="costo-transportista", catalog_type=CatalogType.COST_TYPE
        ),
        currency=currency,
        amount=Decimal("90.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    adjustment_form = FinancialAdjustmentForm(
        data={
            "currency": currency.pk,
            "amount": "30.00",
            "exchange_rate_to_usd": "1",
            "transaction_date": date.today().isoformat(),
            "reference": "REV-001",
            "description": "Compensación parcial de pago duplicado.",
        },
        original=carrier_payment,
    )
    assert adjustment_form.is_valid()
    payment_compensation = create_adjustment(
        original=carrier_payment, form=adjustment_form, actor=user
    )
    user.groups.add(Group.objects.get(name="Dispatcher"))
    confirm_transaction(transaction_entry=payment_compensation, actor=user)
    FinancialTransaction.objects.create(
        order=order,
        movement_type=collection.movement_type,
        currency=currency,
        amount=Decimal("40.00"),
        transaction_date=date.today(),
        status=FinancialStatus.PENDING,
        created_by=user,
    )
    FinancialTransaction.objects.create(
        order=order,
        movement_type=carrier_payment.movement_type,
        cost_type=carrier_payment.cost_type,
        currency=currency,
        amount=Decimal("8.00"),
        transaction_date=date.today(),
        status=FinancialStatus.PENDING,
        created_by=user,
    )

    summary = order_financial_summary(order)

    assert summary["customer_amount_due_usd"] == Decimal("120.00")
    assert summary["customer_received_usd"] == Decimal("130.00")
    assert summary["customer_balance_usd"] == Decimal("-10.00")
    assert summary["customer_credit_usd"] == Decimal("10.00")
    assert summary["carrier_amount_due_usd"] == Decimal("70.00")
    assert summary["carrier_paid_usd"] == Decimal("60.00")
    assert summary["carrier_balance_usd"] == Decimal("10.00")
    assert summary["income_usd"] == Decimal("130.00")
    assert summary["expenses_usd"] == Decimal("60.00")
    assert summary["profit_usd"] == Decimal("70.00")
    assert summary["pending_movements_count"] == 2
    assert summary["pending_movements_usd"] == Decimal("48.00")
    assert payment_compensation.adjustment_of == carrier_payment


@pytest.mark.django_db
def test_compensatory_adjustment_must_reference_confirmed_original(order, user):
    entry = FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="cobro-cliente"),
        currency=CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY),
        amount=Decimal("50.00"),
        transaction_date=date.today(),
        created_by=user,
    )
    adjustment = FinancialTransaction(
        order=order,
        movement_type=entry.movement_type,
        currency=entry.currency,
        amount=Decimal("10.00"),
        transaction_date=date.today(),
        created_by=user,
        adjustment_of=entry,
    )

    with pytest.raises(ValidationError):
        adjustment.full_clean()


@pytest.mark.django_db
def test_only_dispatcher_confirms_financial_transaction(order, user):
    entry = FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="cobro-cliente"),
        currency=CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY),
        amount=Decimal("100"),
        transaction_date=date.today(),
        created_by=user,
    )

    with pytest.raises(ValidationError):
        confirm_transaction(transaction_entry=entry, actor=user)

    user.groups.add(Group.objects.get(name="Dispatcher"))
    confirm_transaction(transaction_entry=entry, actor=user)

    entry.refresh_from_db()
    assert entry.status == FinancialStatus.CONFIRMED
    audit_event = AuditEvent.objects.get(
        action="confirm_financial_transaction", entity_id=str(entry.pk)
    )
    assert audit_event.order == order
    assert audit_event.metadata == {"status": FinancialStatus.CONFIRMED}


@pytest.mark.django_db
def test_only_administrative_manager_validates_summary(order, user):
    with pytest.raises(ValidationError):
        validate_financial_summary(order=order, actor=user)

    user.groups.add(Group.objects.get(name="Gerente administrativo"))
    review = validate_financial_summary(order=order, actor=user, observation="Revisión completa.")

    assert review.status == "validated"
    assert review.reviewed_by == user


def manager(name, username):
    manager_user = get_user_model().objects.create_user(username=username, password="test-pass-123")
    manager_user.groups.add(Group.objects.get(name=name))
    return manager_user


def add_confirmed_finances(order, user, income, expense):
    currency = CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY)
    FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="cobro-cliente"),
        currency=currency,
        amount=income,
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    FinancialTransaction.objects.create(
        order=order,
        movement_type=CatalogEntry.objects.get(code="pago-transportista"),
        cost_type=CatalogEntry.objects.get(
            code="costo-transportista", catalog_type=CatalogType.COST_TYPE
        ),
        currency=currency,
        amount=expense,
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )


@pytest.mark.django_db
def test_commission_uses_profit_rate_and_customer_discount(order, user):
    administrative = manager("Gerente administrativo", "commission-admin")
    add_confirmed_finances(order, user, Decimal("1000"), Decimal("700"))
    validate_financial_summary(order=order, actor=administrative)
    rule = CommissionRule.objects.create(
        broker=order.broker,
        percentage=Decimal("10"),
        valid_from=order.delivery_date - timedelta(days=1),
        created_by=administrative,
    )

    commission = calculate_commission(
        order=order, actor=administrative, customer_unpaid_discount=Decimal("5")
    )

    assert commission.rule == rule
    assert commission.gross_profit_usd == Decimal("300.00")
    assert commission.gross_commission_usd == Decimal("30.00")
    assert commission.commission_amount_usd == Decimal("25.00")
    assert commission.loss_amount_usd == Decimal("0.00")


@pytest.mark.django_db
def test_negative_profit_has_zero_commission_and_requires_loss_agreement(order, user):
    administrative = manager("Gerente administrativo", "loss-admin")
    general = manager("Gerente general", "loss-general")
    add_confirmed_finances(order, user, Decimal("100"), Decimal("200"))
    validate_financial_summary(order=order, actor=administrative)
    CommissionRule.objects.create(
        broker=order.broker,
        percentage=Decimal("10"),
        valid_from=order.delivery_date - timedelta(days=1),
        created_by=administrative,
    )
    commission = calculate_commission(order=order, actor=administrative)

    assert commission.commission_amount_usd == Decimal("0.00")
    assert commission.loss_amount_usd == Decimal("100.00")
    with pytest.raises(ValidationError):
        authorize_commission(commission=commission, actor=general)

    record_loss_agreement(
        commission=commission,
        actor=general,
        company_covered_loss=Decimal("40"),
        agreed_broker_debt=Decimal("60"),
        responsibility_percentage=Decimal("60"),
        loss_report="Cliente no pagó el despacho.",
        negotiation_agreement="Se acordó distribuir la pérdida.",
    )
    authorize_commission(commission=commission, actor=general)

    debt = BrokerDebt.objects.get(origin_commission=commission)
    assert debt.balance_usd == Decimal("60.00")
    assert commission.status == "authorized"


@pytest.mark.django_db
def test_debt_can_be_applied_partially_to_future_commission(order, user):
    administrative = manager("Gerente administrativo", "debt-admin")
    general = manager("Gerente general", "debt-general")
    add_confirmed_finances(order, user, Decimal("100"), Decimal("200"))
    validate_financial_summary(order=order, actor=administrative)
    CommissionRule.objects.create(
        broker=order.broker,
        percentage=Decimal("10"),
        valid_from=order.delivery_date - timedelta(days=1),
        created_by=administrative,
    )
    loss_commission = calculate_commission(order=order, actor=administrative)
    record_loss_agreement(
        commission=loss_commission,
        actor=general,
        company_covered_loss=Decimal("50"),
        agreed_broker_debt=Decimal("50"),
        responsibility_percentage=Decimal("50"),
        loss_report="Informe de pérdida.",
        negotiation_agreement="Acuerdo negociado.",
    )

    order.number = "ORD-2026-000099"
    order.pk = None
    order.save()
    add_confirmed_finances(order, user, Decimal("1000"), Decimal("700"))
    validate_financial_summary(order=order, actor=administrative)
    future_commission = calculate_commission(order=order, actor=administrative)
    debt = BrokerDebt.objects.get(origin_commission=loss_commission)
    application = apply_debt_to_commission(
        debt=debt, commission=future_commission, amount=Decimal("20"), actor=general
    )

    assert application.amount_usd == Decimal("20.00")
    assert debt.balance_usd == Decimal("30.00")
    assert future_commission.payable_amount_usd == Decimal("10.00")


@pytest.mark.django_db
def test_only_general_manager_authorizes_and_records_payment(order, user):
    administrative = manager("Gerente administrativo", "pay-admin")
    general = manager("Gerente general", "pay-general")
    add_confirmed_finances(order, user, Decimal("1000"), Decimal("700"))
    validate_financial_summary(order=order, actor=administrative)
    CommissionRule.objects.create(
        broker=order.broker,
        percentage=Decimal("10"),
        valid_from=order.delivery_date - timedelta(days=1),
        created_by=administrative,
    )
    commission = calculate_commission(order=order, actor=administrative)

    with pytest.raises(ValidationError):
        authorize_commission(commission=commission, actor=administrative)
    authorize_commission(commission=commission, actor=general)
    with pytest.raises(ValidationError):
        record_commission_payment(
            commission=commission, actor=administrative, payment_method="Transferencia"
        )
    record_commission_payment(
        commission=commission,
        actor=general,
        payment_method="Transferencia",
        payment_reference="TRX-001",
    )

    commission.refresh_from_db()
    assert commission.status == "paid"
    assert commission.payment_method == "Transferencia"


@pytest.mark.django_db
def test_finance_admin_audits_rule_changes_and_disables_transaction_writes():
    from types import SimpleNamespace

    from django.contrib import admin
    from django.test import RequestFactory

    from .admin import CommissionRuleAdmin, FinancialTransactionAdmin

    administrator = get_user_model().objects.create_superuser(
        username="finance-audit-admin",
        email="finance-audit-admin@example.test",
        password="test-pass-123",
    )
    broker = get_user_model().objects.create_user(username="finance-audit-broker")
    broker.groups.add(Group.objects.get(name="Broker"))
    rule = CommissionRule(
        broker=broker,
        percentage=Decimal("10"),
        valid_from=date.today(),
        created_by=administrator,
    )
    request = RequestFactory().post("/admin/finance/commissionrule/add/")
    request.user = administrator
    CommissionRuleAdmin(CommissionRule, admin.site).save_model(
        request, rule, SimpleNamespace(changed_data=["percentage"]), change=False
    )
    event = AuditEvent.objects.get(
        actor=administrator,
        action="create_commission_rule",
        entity_id=str(rule.pk),
    )

    assert event.metadata == {"broker_id": broker.pk}
    assert not CommissionRuleAdmin(CommissionRule, admin.site).has_delete_permission(
        request, rule
    )
    transaction_admin = FinancialTransactionAdmin(FinancialTransaction, admin.site)
    assert not transaction_admin.has_add_permission(request)
    assert not transaction_admin.has_change_permission(request)


@pytest.mark.django_db
def test_transaction_views_create_validate_and_confirm_with_role_checks(client, order, user):
    grant(user, "add_financialtransaction", "view_financialtransaction")
    client.force_login(user)

    page = client.get(reverse("finance:create", args=[order.pk]))
    assert page.status_code == 200
    assert page.context["form"].fields["currency"].initial.code == "usd"

    invalid = client.post(
        reverse("finance:create", args=[order.pk]), data("cobro-cliente", amount="0")
    )
    assert invalid.status_code == 200
    assert "amount" in invalid.context["form"].errors
    assert not FinancialTransaction.objects.filter(order=order).exists()

    response = client.post(
        reverse("finance:create", args=[order.pk]), data("cobro-cliente", amount="125.00")
    )
    entry = FinancialTransaction.objects.get(order=order)
    assert response.status_code == 302
    assert entry.status == FinancialStatus.PENDING
    assert entry.created_by == user
    assert entry.base_amount_usd == Decimal("125.00")
    assert AuditEvent.objects.filter(
        actor=user, order=order, action="create_financial_transaction", entity_id=str(entry.pk)
    ).exists()

    administrator = manager("Administrador", "finance-technical-confirm")
    grant(administrator, "change_financialtransaction")
    client.force_login(administrator)
    rejected_confirmation = client.post(reverse("finance:confirm", args=[entry.pk]))
    assert rejected_confirmation.status_code == 302
    entry.refresh_from_db()
    assert entry.status == FinancialStatus.PENDING
    assert any(
        "Solo el Dispatcher" in str(message)
        for message in get_messages(rejected_confirmation.wsgi_request)
    )

    dispatcher = manager("Dispatcher", "finance-view-confirm-dispatcher")
    grant(dispatcher, "change_financialtransaction", "view_financialtransaction")
    client.force_login(dispatcher)
    confirmation = client.post(reverse("finance:confirm", args=[entry.pk]))
    entry.refresh_from_db()
    assert confirmation.status_code == 302
    assert entry.status == FinancialStatus.CONFIRMED
    assert entry.confirmed_by == dispatcher
    assert AuditEvent.objects.filter(
        actor=dispatcher,
        order=order,
        action="confirm_financial_transaction",
        entity_id=str(entry.pk),
    ).exists()


@pytest.mark.django_db
def test_financial_summary_view_checks_business_role_and_audits_validation(
    client, order
):
    technical_admin = manager("Administrador", "finance-review-technical-admin")
    grant(technical_admin, "change_financialreview")
    client.force_login(technical_admin)

    rejected = client.post(
        reverse("finance:validate", args=[order.pk]),
        {"observation": "Intento con permiso técnico."},
    )

    assert rejected.status_code == 302
    assert not FinancialReview.objects.filter(order=order).exists()
    assert any(
        "Solo la Gerencia administrativa" in str(message)
        for message in get_messages(rejected.wsgi_request)
    )

    administrative = manager("Gerente administrativo", "finance-review-approved-admin")
    grant(administrative, "change_financialreview")
    client.force_login(administrative)
    response = client.post(
        reverse("finance:validate", args=[order.pk]),
        {"observation": "Comprobantes revisados."},
    )

    review = FinancialReview.objects.get(order=order)
    assert response.status_code == 302
    assert review.status == "validated"
    assert review.reviewed_by == administrative
    assert review.observation == "Comprobantes revisados."
    assert AuditEvent.objects.filter(
        actor=administrative,
        order=order,
        action="validate_financial_summary",
        entity_id=str(review.pk),
    ).exists()


@pytest.mark.django_db
def test_adjustment_view_creates_compensation_and_rejects_adjusting_an_adjustment(
    client, order, user
):
    dispatcher = manager("Dispatcher", "finance-adjustment-view-dispatcher")
    grant(dispatcher, "add_financialtransaction")
    currency = CatalogEntry.objects.get(code="usd", catalog_type=CatalogType.CURRENCY)
    movement_type = CatalogEntry.objects.get(code="pago-transportista")
    cost_type = CatalogEntry.objects.get(code="costo-transportista")
    pending_original = FinancialTransaction.objects.create(
        order=order,
        movement_type=movement_type,
        cost_type=cost_type,
        currency=currency,
        amount=Decimal("50.00"),
        transaction_date=date.today(),
        status=FinancialStatus.PENDING,
        created_by=user,
    )
    client.force_login(dispatcher)
    invalid_adjustment = client.post(
        reverse("finance:adjustment", args=[pending_original.pk]),
        {
            "currency": currency.pk,
            "amount": "0",
            "exchange_rate_to_usd": "1",
            "transaction_date": date.today().isoformat(),
            "reference": "COMP-INVALID",
            "description": "El monto cero no es válido.",
        },
    )
    assert invalid_adjustment.status_code == 200
    assert "amount" in invalid_adjustment.context["form"].errors

    rejected = client.post(
        reverse("finance:adjustment", args=[pending_original.pk]),
        {
            "currency": currency.pk,
            "amount": "10.00",
            "exchange_rate_to_usd": "1",
            "transaction_date": date.today().isoformat(),
            "reference": "COMP-PEND",
            "description": "No debe ajustar un movimiento pendiente.",
        },
    )
    assert rejected.status_code == 200
    assert not FinancialTransaction.objects.filter(adjustment_of=pending_original).exists()

    original = FinancialTransaction.objects.create(
        order=order,
        movement_type=movement_type,
        cost_type=cost_type,
        currency=currency,
        amount=Decimal("100.00"),
        transaction_date=date.today(),
        status=FinancialStatus.CONFIRMED,
        created_by=user,
    )
    page = client.get(reverse("finance:adjustment", args=[original.pk]))
    response = client.post(
        reverse("finance:adjustment", args=[original.pk]),
        {
            "currency": currency.pk,
            "amount": "25.00",
            "exchange_rate_to_usd": "1",
            "transaction_date": date.today().isoformat(),
            "reference": "COMP-25",
            "description": "Compensación parcial autorizada.",
        },
    )

    adjustment = FinancialTransaction.objects.get(adjustment_of=original)
    assert page.status_code == 200
    assert response.status_code == 302
    assert adjustment.order == order
    assert adjustment.movement_type == movement_type
    assert adjustment.cost_type == cost_type
    assert adjustment.created_by == dispatcher
    assert adjustment.status == FinancialStatus.PENDING
    assert AuditEvent.objects.filter(
        actor=dispatcher,
        order=order,
        action="create_financial_adjustment",
        entity_id=str(adjustment.pk),
    ).exists()

    nested_adjustment = client.get(reverse("finance:adjustment", args=[adjustment.pk]))
    assert nested_adjustment.status_code == 302
    assert FinancialTransaction.objects.filter(order=order).count() == 3


@pytest.mark.django_db
def test_commission_views_calculate_list_detail_authorize_and_pay(client, order, user):
    administrative = manager("Gerente administrativo", "commission-view-admin")
    general = manager("Gerente general", "commission-view-general")
    grant(administrative, "add_commission", "change_commission", "view_commission")
    grant(general, "change_commission", "view_commission")
    add_confirmed_finances(order, user, Decimal("1000.00"), Decimal("700.00"))
    validate_financial_summary(order=order, actor=administrative)
    rule = CommissionRule.objects.create(
        broker=order.broker,
        percentage=Decimal("10.00"),
        valid_from=order.delivery_date - timedelta(days=1),
        created_by=administrative,
    )
    client.force_login(administrative)

    commission_list = client.get(reverse("finance:commission-list"))
    calculate_page = client.get(reverse("finance:commission-calculate", args=[order.pk]))
    invalid_calculation = client.post(
        reverse("finance:commission-calculate", args=[order.pk]),
        {"customer_unpaid_discount": "-1.00"},
    )
    assert commission_list.status_code == 200
    assert not list(commission_list.context["commissions"])
    assert calculate_page.status_code == 200
    assert invalid_calculation.status_code == 200
    assert "customer_unpaid_discount" in invalid_calculation.context["form"].errors

    response = client.post(
        reverse("finance:commission-calculate", args=[order.pk]),
        {"customer_unpaid_discount": "5.00"},
    )
    commission = Commission.objects.get(order=order)
    assert response.status_code == 302
    assert commission.rule == rule
    assert commission.commission_amount_usd == Decimal("25.00")
    assert AuditEvent.objects.filter(
        actor=administrative,
        order=order,
        action="calculate_commission",
        entity_id=str(commission.pk),
    ).exists()

    commission_list = client.get(reverse("finance:commission-list"))
    detail = client.get(reverse("finance:commission-detail", args=[commission.pk]))
    assert list(commission_list.context["commissions"]) == [commission]
    assert detail.status_code == 200
    assert detail.context["commission"] == commission

    rejected_authorization = client.post(
        reverse("finance:commission-authorize", args=[commission.pk])
    )
    commission.refresh_from_db()
    assert rejected_authorization.status_code == 302
    assert commission.status == "calculated"

    client.force_login(general)
    authorization = client.post(reverse("finance:commission-authorize", args=[commission.pk]))
    commission.refresh_from_db()
    assert authorization.status_code == 302
    assert commission.status == "authorized"
    assert commission.authorized_by == general
    authorized_detail = client.get(reverse("finance:commission-detail", args=[commission.pk]))
    assert authorized_detail.status_code == 200
    assert general.username in authorized_detail.content.decode()
    assert "Autorización" in authorized_detail.content.decode()

    client.force_login(administrative)
    rejected_payment = client.post(
        reverse("finance:commission-pay", args=[commission.pk]),
        {"payment_method": "Transferencia", "payment_reference": "TRX-ROLE-001"},
    )
    commission.refresh_from_db()
    assert rejected_payment.status_code == 302
    assert commission.status == "authorized"

    client.force_login(general)
    invalid_payment = client.post(
        reverse("finance:commission-pay", args=[commission.pk]), {}
    )
    assert invalid_payment.status_code == 302
    assert Commission.objects.get(pk=commission.pk).status == "authorized"

    payment = client.post(
        reverse("finance:commission-pay", args=[commission.pk]),
        {"payment_method": "Transferencia", "payment_reference": "TRX-VIEW-001"},
    )
    commission.refresh_from_db()
    assert payment.status_code == 302
    assert commission.status == "paid"
    assert commission.paid_by == general
    assert commission.payment_reference == "TRX-VIEW-001"
    assert AuditEvent.objects.filter(
        actor=general,
        order=order,
        action="record_commission_payment",
        entity_id=str(commission.pk),
    ).exists()
    paid_detail = client.get(reverse("finance:commission-detail", args=[commission.pk]))
    paid_content = paid_detail.content.decode()
    assert paid_detail.status_code == 200
    assert "Pago externo registrado" in paid_content
    assert general.username in paid_content
    assert "Transferencia" in paid_content
    assert "TRX-VIEW-001" in paid_content
    assert commission.paid_at.strftime("%Y") in paid_content


@pytest.mark.django_db
def test_commission_calculation_view_requires_validated_financial_summary(client, order):
    administrative = manager("Gerente administrativo", "commission-view-without-review")
    grant(administrative, "add_commission")
    client.force_login(administrative)

    response = client.post(
        reverse("finance:commission-calculate", args=[order.pk]),
        {"customer_unpaid_discount": "0.00"},
    )

    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert not Commission.objects.filter(order=order).exists()


@pytest.mark.django_db
def test_commission_loss_and_debt_application_views_validate_and_audit(
    client, order, user
):
    administrative = manager("Gerente administrativo", "loss-view-admin")
    general = manager("Gerente general", "loss-view-general")
    grant(general, "change_commission", "view_commission")
    add_confirmed_finances(order, user, Decimal("100.00"), Decimal("200.00"))
    validate_financial_summary(order=order, actor=administrative)
    CommissionRule.objects.create(
        broker=order.broker,
        percentage=Decimal("10.00"),
        valid_from=order.delivery_date - timedelta(days=1),
        created_by=administrative,
    )
    loss_commission = calculate_commission(order=order, actor=administrative)
    client.force_login(general)

    detail = client.get(reverse("finance:commission-detail", args=[loss_commission.pk]))
    invalid_loss_form = client.post(
        reverse("finance:commission-loss", args=[loss_commission.pk]), {}
    )
    rejected_loss_agreement = client.post(
        reverse("finance:commission-loss", args=[loss_commission.pk]),
        {
            "company_covered_loss": "20.00",
            "agreed_broker_debt": "20.00",
            "responsibility_percentage": "50.00",
            "loss_report": "Distribución incompleta.",
            "negotiation_agreement": "La cobertura no suma la pérdida.",
        },
    )
    assert invalid_loss_form.status_code == 302
    assert rejected_loss_agreement.status_code == 302
    assert not BrokerDebt.objects.filter(origin_commission=loss_commission).exists()

    loss = client.post(
        reverse("finance:commission-loss", args=[loss_commission.pk]),
        {
            "company_covered_loss": "40.00",
            "agreed_broker_debt": "60.00",
            "responsibility_percentage": "60.00",
            "loss_report": "Pérdida ficticia registrada.",
            "negotiation_agreement": "Acuerdo ficticio aceptado.",
        },
    )
    debt = BrokerDebt.objects.get(origin_commission=loss_commission)
    assert detail.status_code == 200
    assert loss.status_code == 302
    assert debt.balance_usd == Decimal("60.00")

    future_order = Order.objects.create(
        status=order.status,
        customer=order.customer,
        proposed_carrier=order.proposed_carrier,
        broker=order.broker,
        created_by=order.created_by,
        cargo_type=order.cargo_type,
        equipment_type=order.equipment_type,
        origin=order.origin,
        destination=order.destination,
        pickup_date=order.pickup_date,
        delivery_date=order.delivery_date,
        customer_rate=order.customer_rate,
        carrier_cost=order.carrier_cost,
        number="ORD-FIN-DEBT-VIEW-02",
    )
    add_confirmed_finances(future_order, user, Decimal("1000.00"), Decimal("700.00"))
    validate_financial_summary(order=future_order, actor=administrative)
    future_commission = calculate_commission(order=future_order, actor=administrative)

    invalid_application = client.post(
        reverse("finance:debt-apply", args=[future_commission.pk]),
        {"debt_id": debt.pk, "amount": "0"},
    )
    assert invalid_application.status_code == 302
    assert debt.applications.count() == 0

    application = client.post(
        reverse("finance:debt-apply", args=[future_commission.pk]),
        {"debt_id": debt.pk, "amount": "20.00"},
    )
    debt.refresh_from_db()
    assert application.status_code == 302
    assert debt.balance_usd == Decimal("40.00")
    assert future_commission.debt_applications.get().amount_usd == Decimal("20.00")

    excessive_application = client.post(
        reverse("finance:debt-apply", args=[future_commission.pk]),
        {"debt_id": debt.pk, "amount": "100.00"},
    )
    debt.refresh_from_db()
    assert excessive_application.status_code == 302
    assert debt.balance_usd == Decimal("40.00")
    assert future_commission.debt_applications.count() == 1


@pytest.mark.django_db
def test_commission_rule_views_create_update_validate_and_scope_brokers(
    client,
):
    administrative = manager("Gerente administrativo", "rule-view-admin")
    grant(administrative, "add_commissionrule", "change_commissionrule", "view_commissionrule")
    broker = manager("Broker", "rule-view-broker")
    other_broker = manager("Broker", "rule-view-other-broker")
    client.force_login(administrative)

    rules_page = client.get(reverse("finance:commission-rules"))
    create_page = client.get(reverse("finance:commission-rule-create"))
    rule_data = {
        "broker": broker.pk,
        "percentage": "12.50",
        "valid_from": date.today().isoformat(),
        "valid_to": "",
        "is_active": "on",
    }
    created = client.post(reverse("finance:commission-rule-create"), rule_data)
    rule = CommissionRule.objects.get(broker=broker)
    assert rules_page.status_code == 200
    assert create_page.status_code == 200
    assert created.status_code == 302
    assert rule.created_by == administrative
    assert AuditEvent.objects.filter(
        actor=administrative, action="create_commission_rule", entity_id=str(rule.pk)
    ).exists()

    updated = client.post(
        reverse("finance:commission-rule-edit", args=[rule.pk]),
        {**rule_data, "percentage": "15.00"},
    )
    rule.refresh_from_db()
    assert updated.status_code == 302
    assert rule.percentage == Decimal("15.00")
    assert AuditEvent.objects.filter(
        actor=administrative, action="update_commission_rule", entity_id=str(rule.pk)
    ).exists()

    overlapping = client.post(
        reverse("finance:commission-rule-create"), rule_data
    )
    assert overlapping.status_code == 200
    assert "valid_from" in overlapping.context["form"].errors
    assert CommissionRule.objects.filter(broker=broker).count() == 1

    other_rule = CommissionRule.objects.create(
        broker=other_broker,
        percentage=Decimal("8.00"),
        valid_from=date.today(),
        created_by=administrative,
    )
    grant(broker, "view_commissionrule", "change_commissionrule")
    client.force_login(broker)
    scoped_rules = client.get(reverse("finance:commission-rules"))
    inaccessible_edit = client.get(
        reverse("finance:commission-rule-edit", args=[other_rule.pk])
    )
    assert list(scoped_rules.context["rules"]) == [rule]
    assert inaccessible_edit.status_code == 404

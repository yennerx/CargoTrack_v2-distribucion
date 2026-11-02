from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.catalogs.models import CatalogEntry, CatalogType
from apps.orders.models import Order


class FinancialStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    CONFIRMED = "confirmed", "Confirmado"
    VOIDED = "voided", "Anulado"


class ReviewStatus(models.TextChoices):
    PENDING = "pending", "Pendiente"
    VALIDATED = "validated", "Validado"
    REJECTED = "rejected", "Rechazado"


class CommissionStatus(models.TextChoices):
    CALCULATED = "calculated", "Calculada"
    AUTHORIZED = "authorized", "Autorizada"
    PAID = "paid", "Pagada"
    VOIDED = "voided", "Anulada"


class DebtStatus(models.TextChoices):
    OPEN = "open", "Pendiente"
    SETTLED = "settled", "Saldada"
    VOIDED = "voided", "Anulada"


class CommercialAdjustmentTarget(models.TextChoices):
    CUSTOMER = "customer", "Cliente"
    CARRIER = "carrier", "Transportista"


class CommercialAdjustmentStatus(models.TextChoices):
    PENDING = "pending", "Pendiente de aprobación"
    APPROVED = "approved", "Aprobado"
    REJECTED = "rejected", "Rechazado"


class FinancialTransaction(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="financial_transactions"
    )
    movement_type = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="financial_transactions",
        limit_choices_to={"catalog_type": CatalogType.FINANCIAL_MOVEMENT},
    )
    cost_type = models.ForeignKey(
        CatalogEntry,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="cost_transactions",
        limit_choices_to={"catalog_type": CatalogType.COST_TYPE},
    )
    currency = models.ForeignKey(
        CatalogEntry,
        on_delete=models.PROTECT,
        related_name="financial_transactions_currency",
        limit_choices_to={"catalog_type": CatalogType.CURRENCY},
    )
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    exchange_rate_to_usd = models.DecimalField(
        max_digits=14, decimal_places=6, default=Decimal("1")
    )
    base_amount_usd = models.DecimalField(max_digits=14, decimal_places=2, blank=True)
    status = models.CharField(
        max_length=20, choices=FinancialStatus.choices, default=FinancialStatus.PENDING
    )
    transaction_date = models.DateField()
    reference = models.CharField(max_length=120, blank=True)
    description = models.TextField(blank=True)
    adjustment_of = models.ForeignKey(
        "self", blank=True, null=True, on_delete=models.PROTECT, related_name="adjustments"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_financial_transactions",
    )
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, blank=True, null=True, on_delete=models.SET_NULL,
        related_name="confirmed_financial_transactions"
    )
    confirmed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-transaction_date", "-created_at")

    def clean(self):
        errors = {}
        if self.amount is not None and self.amount <= 0:
            errors["amount"] = "El monto debe ser mayor que cero."
        if self.exchange_rate_to_usd is not None and self.exchange_rate_to_usd <= 0:
            errors["exchange_rate_to_usd"] = "La tasa de cambio debe ser mayor que cero."
        if (
            self.movement_type_id
            and self.movement_type.catalog_type != CatalogType.FINANCIAL_MOVEMENT
        ):
            errors["movement_type"] = "Seleccione un movimiento financiero válido."
        if self.cost_type_id and self.cost_type.catalog_type != CatalogType.COST_TYPE:
            errors["cost_type"] = "Seleccione un tipo de costo válido."
        if self.currency_id and self.currency.catalog_type != CatalogType.CURRENCY:
            errors["currency"] = "Seleccione una moneda válida."
        if self.movement_type_id and self.movement_type.code in {
            "gasto-transporte", "otro-gasto", "pago-transportista"
        } and not self.cost_type_id:
            errors["cost_type"] = "Seleccione el tipo de costo para este egreso."
        if self.movement_type_id and self.movement_type.code == "impuesto":
            errors["movement_type"] = (
                "Los impuestos se calculan anualmente y no se registran por orden."
            )
        if self.adjustment_of_id:
            if self.adjustment_of.status != FinancialStatus.CONFIRMED:
                errors["adjustment_of"] = "Solo se puede compensar un movimiento confirmado."
            if self.adjustment_of.adjustment_of_id:
                errors["adjustment_of"] = "La corrección debe apuntar al movimiento original."
            if self.order_id and self.order_id != self.adjustment_of.order_id:
                errors["order"] = "La corrección debe pertenecer a la orden original."
            if (
                self.movement_type_id
                and self.movement_type_id != self.adjustment_of.movement_type_id
            ):
                errors["movement_type"] = (
                    "La corrección debe conservar el tipo de movimiento original."
                )
            if self.cost_type_id != self.adjustment_of.cost_type_id:
                errors["cost_type"] = "La corrección debe conservar el tipo de costo original."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        self.base_amount_usd = (self.amount * self.exchange_rate_to_usd).quantize(Decimal("0.01"))
        super().save(*args, **kwargs)

    @property
    def is_income(self):
        return self.movement_type.code == "cobro-cliente"

    def __str__(self):
        return f"{self.order.number} - {self.movement_type.name} - {self.amount}"


class FinancialReview(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="financial_review")
    status = models.CharField(
        max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    observation = models.TextField(blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.SET_NULL,
        related_name="financial_reviews",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)


class CommissionRule(models.Model):
    broker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commission_rules"
    )
    percentage = models.DecimalField(max_digits=5, decimal_places=2)
    valid_from = models.DateField()
    valid_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="created_commission_rules"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("broker", "-valid_from", "-created_at")

    def clean(self):
        errors = {}
        if self.percentage is not None and not 0 <= self.percentage <= 100:
            errors["percentage"] = "El porcentaje debe estar entre 0 y 100."
        if self.valid_to and self.valid_to < self.valid_from:
            errors["valid_to"] = "La vigencia final no puede ser anterior a la inicial."
        if self.broker_id and self.valid_from:
            from django.db.models import Q

            overlapping = CommissionRule.objects.filter(
                broker_id=self.broker_id,
                is_active=True,
                valid_from__lte=self.valid_to or self.valid_from,
            ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=self.valid_from))
            if self.pk:
                overlapping = overlapping.exclude(pk=self.pk)
            if overlapping.exists():
                errors["valid_from"] = "El broker ya tiene una regla vigente en ese período."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"{self.broker} - {self.percentage}% desde {self.valid_from}"


class Commission(models.Model):
    order = models.OneToOneField(Order, on_delete=models.PROTECT, related_name="commission")
    broker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="commissions"
    )
    rule = models.ForeignKey(CommissionRule, on_delete=models.PROTECT, related_name="commissions")
    gross_profit_usd = models.DecimalField(max_digits=14, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=5, decimal_places=2)
    gross_commission_usd = models.DecimalField(max_digits=14, decimal_places=2)
    customer_unpaid_discount_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0")
    )
    commission_amount_usd = models.DecimalField(max_digits=14, decimal_places=2)
    loss_amount_usd = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0"))
    company_covered_loss_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0")
    )
    agreed_broker_debt_usd = models.DecimalField(
        max_digits=14, decimal_places=2, default=Decimal("0")
    )
    status = models.CharField(
        max_length=20, choices=CommissionStatus.choices, default=CommissionStatus.CALCULATED
    )
    loss_report = models.TextField(blank=True)
    negotiation_agreement = models.TextField(blank=True)
    calculated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="calculated_commissions"
    )
    calculated_at = models.DateTimeField(auto_now_add=True)
    authorized_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="authorized_commissions",
    )
    authorized_at = models.DateTimeField(blank=True, null=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="paid_commissions",
    )
    paid_at = models.DateTimeField(blank=True, null=True)
    payment_method = models.CharField(max_length=40, blank=True)
    payment_reference = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-calculated_at",)

    def clean(self):
        errors = {}
        if self.commission_rate is not None and not 0 <= self.commission_rate <= 100:
            errors["commission_rate"] = "El porcentaje debe estar entre 0 y 100."
        for field in (
            "customer_unpaid_discount_usd",
            "company_covered_loss_usd",
            "agreed_broker_debt_usd",
        ):
            if getattr(self, field) is not None and getattr(self, field) < 0:
                errors[field] = "El monto no puede ser negativo."
        if self.status == CommissionStatus.PAID and not self.paid_at:
            errors["paid_at"] = "Una comisión pagada debe tener fecha de pago."
        if errors:
            raise ValidationError(errors)

    @property
    def applied_debt_usd(self):
        return sum(
            (application.amount_usd for application in self.debt_applications.all()),
            start=Decimal("0"),
        )

    @property
    def payable_amount_usd(self):
        return max(self.commission_amount_usd - self.applied_debt_usd, Decimal("0"))

    def __str__(self):
        return f"Comisión {self.order.number} - {self.broker}"


class BrokerDebt(models.Model):
    broker = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="broker_debts"
    )
    origin_commission = models.OneToOneField(
        Commission, on_delete=models.PROTECT, related_name="broker_debt"
    )
    loss_report = models.TextField()
    negotiation_agreement = models.TextField()
    loss_amount_usd = models.DecimalField(max_digits=14, decimal_places=2)
    company_covered_loss_usd = models.DecimalField(max_digits=14, decimal_places=2)
    agreed_amount_usd = models.DecimalField(max_digits=14, decimal_places=2)
    balance_usd = models.DecimalField(max_digits=14, decimal_places=2)
    responsibility_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    status = models.CharField(max_length=20, choices=DebtStatus.choices, default=DebtStatus.OPEN)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="approved_broker_debts"
    )
    approved_at = models.DateTimeField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        errors = {}
        if self.agreed_amount_usd is not None and self.agreed_amount_usd < 0:
            errors["agreed_amount_usd"] = "La deuda acordada no puede ser negativa."
        if self.balance_usd is not None and self.balance_usd < 0:
            errors["balance_usd"] = "El saldo no puede ser negativo."
        if self.responsibility_percentage is not None and not (
            0 <= self.responsibility_percentage <= 100
        ):
            errors["responsibility_percentage"] = "La responsabilidad debe estar entre 0 y 100."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Deuda de {self.broker} - {self.balance_usd} USD"


class CommissionDebtApplication(models.Model):
    debt = models.ForeignKey(BrokerDebt, on_delete=models.PROTECT, related_name="applications")
    commission = models.ForeignKey(
        Commission, on_delete=models.PROTECT, related_name="debt_applications"
    )
    amount_usd = models.DecimalField(max_digits=14, decimal_places=2)
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="commission_debt_applications",
    )
    applied_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("debt", "commission"), name="unique_debt_commission_application"
            )
        ]

    def clean(self):
        if self.amount_usd is not None and self.amount_usd <= 0:
            raise ValidationError({"amount_usd": "La aplicación debe ser mayor que cero."})


class CommercialAdjustment(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.PROTECT, related_name="commercial_adjustments"
    )
    target = models.CharField(max_length=20, choices=CommercialAdjustmentTarget.choices)
    amount_usd = models.DecimalField(max_digits=14, decimal_places=2)
    reason = models.TextField()
    reference = models.CharField(max_length=120, blank=True)
    status = models.CharField(
        max_length=20,
        choices=CommercialAdjustmentStatus.choices,
        default=CommercialAdjustmentStatus.PENDING,
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_commercial_adjustments",
    )
    requested_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        on_delete=models.PROTECT,
        related_name="reviewed_commercial_adjustments",
    )
    reviewed_at = models.DateTimeField(blank=True, null=True)
    review_observation = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ("-requested_at",)
        indexes = [
            models.Index(fields=("order", "status"), name="finance_com_order_9c62d4_idx"),
            models.Index(fields=("target", "status"), name="finance_com_target_42e52e_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(amount_usd=0),
                name="commercial_adjustment_nonzero",
            ),
        ]

    def clean(self):
        errors = {}
        if self.amount_usd == 0:
            errors["amount_usd"] = (
                "El ajuste debe ser distinto de cero. Use + para aumentar y - para reducir."
            )
        if not self.reason or not self.reason.strip():
            errors["reason"] = "Indique el motivo o acuerdo que respalda el ajuste."
        if self.target not in CommercialAdjustmentTarget.values:
            errors["target"] = "Seleccione si el ajuste corresponde al cliente o al transportista."
        if errors:
            raise ValidationError(errors)

    def __str__(self):
        return f"Ajuste {self.get_target_display()} {self.amount_usd} USD - {self.order.number}"

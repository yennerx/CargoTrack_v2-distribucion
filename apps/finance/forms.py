from django import forms
from django.db.models import Q

from apps.catalogs.models import CatalogEntry, CatalogType

from .models import (
    CommercialAdjustmentTarget,
    CommissionRule,
    FinancialTransaction,
)


class FinancialTransactionForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = (
            "movement_type", "cost_type", "currency", "amount", "exchange_rate_to_usd",
            "transaction_date", "reference", "description",
        )
        labels = {
            "movement_type": "Tipo de movimiento", "cost_type": "Tipo de costo",
            "currency": "Moneda", "amount": "Monto", "exchange_rate_to_usd": "Tasa a USD",
            "transaction_date": "Fecha", "reference": "Referencia", "description": "Descripción",
        }
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["movement_type"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.FINANCIAL_MOVEMENT, is_active=True
        )
        self.fields["cost_type"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.COST_TYPE, is_active=True
        )
        self.fields["currency"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.CURRENCY, is_active=True
        )
        self.fields["currency"].initial = CatalogEntry.objects.filter(
            catalog_type=CatalogType.CURRENCY, code="usd", is_active=True
        ).first()
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class FinancialAdjustmentForm(forms.ModelForm):
    class Meta:
        model = FinancialTransaction
        fields = (
            "currency",
            "amount",
            "exchange_rate_to_usd",
            "transaction_date",
            "reference",
            "description",
        )
        labels = {
            "currency": "Moneda",
            "amount": "Monto compensatorio",
            "exchange_rate_to_usd": "Tasa a USD",
            "transaction_date": "Fecha",
            "reference": "Referencia",
            "description": "Motivo y detalle",
        }
        widgets = {
            "transaction_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, original, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["currency"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.CURRENCY
        ).filter(Q(is_active=True) | Q(pk=original.currency_id))
        self.fields["currency"].initial = original.currency
        self.fields["amount"].help_text = "Indique el monto que compensa el movimiento original."
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class CommercialAdjustmentForm(forms.Form):
    target = forms.ChoiceField(
        label="Monto pactado para",
        choices=CommercialAdjustmentTarget.choices,
    )
    amount_usd = forms.DecimalField(
        label="Ajuste (USD)",
        max_digits=14,
        decimal_places=2,
        help_text="Use un monto positivo para aumentar o negativo para reducir el monto exigible.",
    )
    reason = forms.CharField(
        label="Motivo o acuerdo comercial",
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    reference = forms.CharField(label="Referencia", max_length=120, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_amount_usd(self):
        amount = self.cleaned_data["amount_usd"]
        if amount == 0:
            raise forms.ValidationError("El ajuste debe ser distinto de cero.")
        return amount


class CommercialAdjustmentReviewForm(forms.Form):
    observation = forms.CharField(
        label="Observación de revisión",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class CommissionRuleForm(forms.ModelForm):
    class Meta:
        model = CommissionRule
        fields = ("broker", "percentage", "valid_from", "valid_to", "is_active")
        labels = {
            "broker": "Broker",
            "percentage": "Porcentaje",
            "valid_from": "Vigente desde",
            "valid_to": "Vigente hasta",
            "is_active": "Activa",
        }
        widgets = {
            "valid_from": forms.DateInput(attrs={"type": "date"}),
            "valid_to": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        self.fields["broker"].queryset = self.fields["broker"].queryset.filter(
            groups__name="Broker", is_active=True
        ).distinct()
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class CommissionCalculationForm(forms.Form):
    customer_unpaid_discount = forms.DecimalField(
        label="Descuento por falta de pago del cliente",
        min_value=0,
        max_digits=14,
        decimal_places=2,
        initial=0,
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["customer_unpaid_discount"].widget.attrs["class"] = "form-control"


class LossAgreementForm(forms.Form):
    company_covered_loss = forms.DecimalField(
        label="Pérdida asumida por la empresa", min_value=0, max_digits=14, decimal_places=2
    )
    agreed_broker_debt = forms.DecimalField(
        label="Deuda acordada del broker", min_value=0, max_digits=14, decimal_places=2
    )
    responsibility_percentage = forms.DecimalField(
        label="Responsabilidad negociada (%)", min_value=0, max_value=100,
        max_digits=5, decimal_places=2,
    )
    loss_report = forms.CharField(
        label="Informe de pérdida", widget=forms.Textarea(attrs={"rows": 4})
    )
    negotiation_agreement = forms.CharField(
        label="Acuerdo con cliente y broker", widget=forms.Textarea(attrs={"rows": 4})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class CommissionPaymentForm(forms.Form):
    payment_method = forms.CharField(label="Método de pago", max_length=40)
    payment_reference = forms.CharField(
        label="Referencia u observación", max_length=120, required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class DebtApplicationForm(forms.Form):
    amount = forms.DecimalField(
        label="Monto a descontar", min_value=0.01, max_digits=14, decimal_places=2
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["amount"].widget.attrs["class"] = "form-control"

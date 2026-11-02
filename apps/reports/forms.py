from django import forms
from django.contrib.auth import get_user_model

from apps.carriers.models import Carrier
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.core.access_scope import has_global_data_access, scope_carriers, scope_customers
from apps.customers.models import Customer
from apps.finance.models import CommissionStatus, FinancialStatus
from apps.orders.models import CLOSURE_CATALOG_CODES, OrderClosureStatus

REPORT_COMMISSION_STATUSES = tuple(
    (value, label)
    for value, label in CommissionStatus.choices
    if value != CommissionStatus.VOIDED
)

REPORT_CHOICES = (
    ("orders", "Reporte de órdenes"),
    ("pending-collections", "Cobros pendientes"),
    ("pending-payments", "Pagos pendientes"),
    ("commissions", "Comisiones por colaborador"),
    ("financial-summary", "Resumen financiero"),
)

LEGACY_REPORT_PRESETS = {
    "orders-status": {"group_by": "status"},
    "orders-customer": {"group_by": "customer"},
    "orders-carrier": {"group_by": "carrier"},
    "orders-broker": {"group_by": "broker"},
    "orders-overdue": {"overdue": "yes"},
}

ORDER_REPORT_SHORTCUTS = (
    ("Órdenes por estado", {"group_by": "status"}),
    ("Órdenes por cliente", {"group_by": "customer"}),
    ("Órdenes por transportista", {"group_by": "carrier"}),
    ("Órdenes por broker", {"group_by": "broker"}),
    ("Órdenes atrasadas", {"overdue": "yes"}),
)


class ReportFilterForm(forms.Form):
    report = forms.ChoiceField(label="Reporte", choices=REPORT_CHOICES)
    date_basis = forms.ChoiceField(
        label="Filtrar por fecha de",
        choices=(("created", "Creación"), ("delivery", "Entrega")),
        required=False,
        initial="created",
    )
    date_from = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    customer = forms.ModelChoiceField(
        label="Cliente", queryset=Customer.objects.none(), required=False
    )
    broker = forms.ModelChoiceField(
        label="Broker", queryset=get_user_model().objects.none(), required=False
    )
    carrier = forms.ModelChoiceField(
        label="Transportista", queryset=Carrier.objects.none(), required=False
    )
    status = forms.ModelChoiceField(
        label="Estado", queryset=CatalogEntry.objects.none(), required=False
    )
    closure_status = forms.ChoiceField(
        label="Estado de cierre",
        choices=(("", "Todos"), *OrderClosureStatus.choices),
        required=False,
    )
    cargo_type = forms.ModelChoiceField(
        label="Tipo de carga", queryset=CatalogEntry.objects.none(), required=False
    )
    financial_status = forms.ChoiceField(
        label="Estado financiero",
        choices=(('', "Todos"), *FinancialStatus.choices),
        required=False,
    )
    commission_status = forms.ChoiceField(
        label="Estado de comisión",
        choices=(('', "Todos"), *REPORT_COMMISSION_STATUSES),
        required=False,
    )
    group_by = forms.ChoiceField(
        label="Agrupar por",
        choices=(
            ("", "Sin agrupar"),
            ("status", "Estado"),
            ("customer", "Cliente"),
            ("carrier", "Transportista"),
            ("broker", "Broker"),
        ),
        required=False,
    )
    overdue = forms.ChoiceField(
        label="Atraso por falta de actualización",
        choices=(("", "Todas"), ("yes", "Solo atrasadas"), ("no", "Excluir atrasadas")),
        required=False,
    )

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        selected_report = (
            self.data.get("report", "") if self.is_bound else self.initial.get("report", "")
        )
        if selected_report != "orders":
            for field_name in (
                "date_basis",
                "group_by",
                "overdue",
                "financial_status",
                "closure_status",
            ):
                self.fields.pop(field_name, None)
        if selected_report != "commissions":
            self.fields.pop("commission_status", None)
        else:
            for field_name in (
                "date_basis",
                "group_by",
                "overdue",
                "financial_status",
                "closure_status",
            ):
                self.fields.pop(field_name, None)
        customers = Customer.objects.order_by("legal_name")
        carriers = Carrier.objects.order_by("legal_name")
        brokers = get_user_model().objects.filter(
            broker_orders__isnull=False
        ).distinct().order_by("username")
        if user is not None:
            customers = scope_customers(customers, user)
            carriers = scope_carriers(carriers, user)
            if not has_global_data_access(user):
                brokers = brokers.filter(pk=user.pk)
        self.fields["customer"].queryset = customers
        self.fields["broker"].queryset = brokers
        self.fields["carrier"].queryset = carriers
        self.fields["status"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.ORDER_STATUS
        ).exclude(code__in=CLOSURE_CATALOG_CODES)
        self.fields["cargo_type"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.CARGO_TYPE
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("date_from") and cleaned_data.get("date_to"):
            if cleaned_data["date_to"] < cleaned_data["date_from"]:
                self.add_error(
                    "date_to", "La fecha final no puede ser anterior a la inicial."
                )
        return cleaned_data

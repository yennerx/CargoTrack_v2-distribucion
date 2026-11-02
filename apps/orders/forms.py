from django import forms

from apps.carriers.models import Carrier
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.core.access_scope import (
    active_brokers,
    broker_can_access_carrier,
    broker_can_access_customer,
    is_broker,
    scope_carriers,
    scope_customers,
)
from apps.customers.models import Customer

from .models import Order


class OrderStatusChangeForm(forms.Form):
    status = forms.ModelChoiceField(queryset=CatalogEntry.objects.none(), label="Nuevo estado")
    observation = forms.CharField(
        label="Observación",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
    )

    def __init__(self, *args, allowed_codes=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.ORDER_STATUS,
            is_active=True,
            code__in=allowed_codes or (),
        )
        self.fields["status"].widget.attrs["class"] = "form-select"

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        observation = cleaned_data.get("observation", "").strip()
        if status and status.code in {"cancelada", "reabierta"} and not observation:
            self.add_error("observation", "La observación es obligatoria para esta transición.")
        return cleaned_data


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = (
            "broker",
            "customer",
            "proposed_carrier",
            "dispatcher",
            "cargo_type",
            "equipment_type",
            "origin",
            "destination",
            "pickup_date",
            "delivery_date",
            "customer_rate",
            "carrier_cost",
            "rate_conditions",
            "logistics_notes",
        )
        labels = {
            "broker": "Broker asignado",
            "customer": "Cliente",
            "proposed_carrier": "Transportista propuesto",
            "dispatcher": "Dispatcher asignado",
            "cargo_type": "Tipo de carga",
            "equipment_type": "Tipo de equipo",
            "origin": "Origen",
            "destination": "Destino",
            "pickup_date": "Fecha de recogida",
            "delivery_date": "Fecha de entrega",
            "customer_rate": "Tarifa al cliente (USD)",
            "carrier_cost": "Costo del transportista (USD)",
            "rate_conditions": "Condiciones de tarifa",
            "logistics_notes": "Notas logísticas",
        }
        widgets = {
            "pickup_date": forms.DateInput(attrs={"type": "date"}),
            "delivery_date": forms.DateInput(attrs={"type": "date"}),
            "rate_conditions": forms.Textarea(attrs={"rows": 3}),
            "logistics_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        if actor and is_broker(actor):
            self.fields.pop("broker")
        else:
            brokers = active_brokers()
            if self.instance.pk:
                brokers = brokers | self.fields["broker"].queryset.filter(
                    pk=self.instance.broker_id
                )
            self.fields["broker"].queryset = brokers.distinct().order_by("username")
            self.fields["broker"].required = bool(actor)

        customers = Customer.objects.filter(is_active=True)
        carriers = Carrier.objects.filter(is_active=True)
        if actor:
            customers = scope_customers(customers, actor)
            carriers = scope_carriers(carriers, actor)
        self.fields["customer"].queryset = customers
        self.fields["proposed_carrier"].queryset = carriers
        self.fields["dispatcher"].queryset = self.fields["dispatcher"].queryset.filter(
            is_active=True, groups__name="Dispatcher"
        ).distinct()
        for _name, field in self.fields.items():
            field.widget.attrs.setdefault("class", "form-control")
        for name, catalog_type in (
            ("cargo_type", CatalogType.CARGO_TYPE),
            ("equipment_type", CatalogType.EQUIPMENT_TYPE),
        ):
            self.fields[name].queryset = CatalogEntry.objects.filter(
                catalog_type=catalog_type, is_active=True
            )

    def clean(self):
        cleaned_data = super().clean()
        broker = cleaned_data.get("broker")
        customer = cleaned_data.get("customer")
        carrier = cleaned_data.get("proposed_carrier")
        if broker and customer and not broker_can_access_customer(broker, customer):
            self.add_error(
                "broker",
                "Asigne primero el cliente al Broker seleccionado.",
            )
        if broker and carrier and not broker_can_access_carrier(broker, carrier):
            self.add_error(
                "broker",
                "Asigne primero el transportista al Broker seleccionado.",
            )
        return cleaned_data

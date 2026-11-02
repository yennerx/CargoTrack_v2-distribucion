import re

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.forms import inlineformset_factory

from apps.catalogs.models import CatalogEntry, CatalogType
from apps.core.access_scope import (
    active_brokers,
    brokers_requiring_master_assignment,
    is_broker,
)
from apps.orders.models import Order

from .models import Carrier, CarrierDocument, CarrierUnit


class CarrierForm(forms.ModelForm):
    class Meta:
        model = Carrier
        fields = (
            "carrier_type",
            "nit",
            "legal_name",
            "commercial_name",
            "address",
            "city",
            "country",
            "primary_phone",
            "email",
            "notes",
            "brokers",
        )
        labels = {
            "carrier_type": "Tipo de transportista",
            "nit": "NIT",
            "legal_name": "Nombre legal o completo",
            "commercial_name": "Nombre comercial",
            "address": "Dirección",
            "city": "Ciudad",
            "country": "País",
            "primary_phone": "Teléfono principal",
            "email": "Correo electrónico",
            "notes": "Observaciones",
            "brokers": "Brokers asignados",
        }
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args, actor=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.actor = actor
        if actor and is_broker(actor):
            self.fields.pop("brokers")
        else:
            broker_queryset = active_brokers()
            if self.instance.pk:
                broker_queryset = get_user_model().objects.filter(
                    Q(pk__in=broker_queryset.values("pk"))
                    | Q(pk__in=self.instance.brokers.values("pk"))
                ).distinct().order_by("username")
            self.fields["brokers"].queryset = broker_queryset
            self.fields["brokers"].required = bool(actor)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean_nit(self):
        nit = re.sub(r"[\s-]+", "", self.cleaned_data["nit"]).upper()
        if not re.fullmatch(r"[A-Z0-9]{3,30}", nit):
            raise forms.ValidationError("Ingrese un NIT válido, sin caracteres especiales.")
        return nit

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and "brokers" in self.fields:
            selected_ids = {
                broker.pk for broker in cleaned_data.get("brokers", ())
            }
            orders = Order.objects.filter(
                Q(proposed_carrier_id=self.instance.pk)
                | Q(confirmed_carrier_id=self.instance.pk)
            )
            required_ids = brokers_requiring_master_assignment(orders)
            required_ids.discard(self.instance.created_by_id)
            if required_ids - selected_ids:
                self.add_error(
                    "brokers",
                    "Mantenga asignados los Brokers que aún tienen órdenes relacionadas.",
                )
        return cleaned_data


class CarrierUnitForm(forms.ModelForm):
    class Meta:
        model = CarrierUnit
        fields = (
            "equipment_type",
            "unit_identifier",
            "license_plate",
            "brand",
            "model",
            "is_active",
        )
        labels = {
            "equipment_type": "Tipo de equipo",
            "unit_identifier": "Identificador de unidad",
            "license_plate": "Placa",
            "brand": "Marca",
            "model": "Modelo",
            "is_active": "Unidad activa",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["equipment_type"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.EQUIPMENT_TYPE,
            is_active=True,
        )
        for name, field in self.fields.items():
            field.widget.attrs["class"] = (
                "form-check-input" if name == "is_active" else "form-control"
            )


class CarrierDocumentForm(forms.ModelForm):
    class Meta:
        model = CarrierDocument
        fields = (
            "document_type",
            "document_number",
            "issued_at",
            "expires_at",
            "notes",
            "is_active",
        )
        labels = {
            "document_type": "Tipo de documento",
            "document_number": "Número de documento",
            "issued_at": "Fecha de emisión",
            "expires_at": "Fecha de vencimiento",
            "notes": "Observaciones",
            "is_active": "Documento activo",
        }
        widgets = {
            "issued_at": forms.DateInput(attrs={"type": "date"}),
            "expires_at": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document_type"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.DOCUMENT_TYPE,
            is_active=True,
        )
        for name, field in self.fields.items():
            field.widget.attrs["class"] = (
                "form-check-input" if name == "is_active" else "form-control"
            )


CarrierUnitFormSet = inlineformset_factory(
    Carrier,
    CarrierUnit,
    form=CarrierUnitForm,
    extra=1,
    can_delete=False,
)
CarrierDocumentFormSet = inlineformset_factory(
    Carrier,
    CarrierDocument,
    form=CarrierDocumentForm,
    extra=1,
    can_delete=False,
)

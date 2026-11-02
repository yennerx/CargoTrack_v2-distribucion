import re

from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import BaseInlineFormSet, inlineformset_factory

from apps.core.access_scope import (
    active_brokers,
    brokers_requiring_master_assignment,
    is_broker,
)
from apps.orders.models import Order

from .models import Customer, CustomerContact


class CustomerForm(forms.ModelForm):
    class Meta:
        model = Customer
        fields = (
            "nit",
            "legal_name",
            "commercial_name",
            "address",
            "city",
            "country",
            "notes",
            "brokers",
        )
        labels = {
            "nit": "NIT",
            "legal_name": "Nombre legal",
            "commercial_name": "Nombre comercial",
            "address": "Dirección",
            "city": "Ciudad",
            "country": "País",
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
                broker_queryset = (
                    get_user_model().objects.filter(
                        Q(pk__in=broker_queryset.values("pk"))
                        | Q(pk__in=self.instance.brokers.values("pk"))
                    )
                    .distinct()
                    .order_by("username")
                )
            self.fields["brokers"].queryset = broker_queryset
            self.fields["brokers"].required = bool(actor)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["nit"].help_text = "Identificador obligatorio y único."

    def clean_nit(self):
        nit = re.sub(r"[\s-]+", "", self.cleaned_data["nit"]).upper()
        if not nit or not re.fullmatch(r"[A-Z0-9]{3,30}", nit):
            raise ValidationError("Ingrese un NIT válido, sin caracteres especiales.")
        return nit

    def clean(self):
        cleaned_data = super().clean()
        if self.instance.pk and "brokers" in self.fields:
            selected_ids = {
                broker.pk for broker in cleaned_data.get("brokers", ())
            }
            orders = Order.objects.filter(customer_id=self.instance.pk)
            required_ids = brokers_requiring_master_assignment(orders)
            required_ids.discard(self.instance.created_by_id)
            if required_ids - selected_ids:
                self.add_error(
                    "brokers",
                    "Mantenga asignados los Brokers que aún tienen órdenes relacionadas.",
                )
        return cleaned_data


class CustomerContactForm(forms.ModelForm):
    class Meta:
        model = CustomerContact
        fields = (
            "name",
            "position",
            "primary_phone",
            "secondary_phone",
            "email",
            "preferred_contact_method",
            "is_primary",
            "is_active",
        )
        labels = {
            "name": "Nombre completo",
            "position": "Cargo",
            "primary_phone": "Teléfono principal",
            "secondary_phone": "Teléfono alternativo",
            "email": "Correo electrónico",
            "preferred_contact_method": "Medio preferido de contacto",
            "is_primary": "Contacto principal",
            "is_active": "Contacto activo",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name, field in self.fields.items():
            field.widget.attrs["class"] = (
                "form-check-input" if name in ("is_primary", "is_active") else "form-control"
            )


class BaseCustomerContactFormSet(BaseInlineFormSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and not self.instance.pk and self.forms:
            self.forms[0].fields["is_primary"].initial = True

    def clean(self):
        super().clean()
        if any(form.errors for form in self.forms):
            return

        active_contacts = [
            form.cleaned_data
            for form in self.forms
            if form.cleaned_data and not form.cleaned_data.get("DELETE", False)
        ]
        if not active_contacts:
            raise ValidationError("Debe registrar al menos un contacto principal.")
        primary_contacts = [
            contact
            for contact in active_contacts
            if contact.get("is_active", True) and contact.get("is_primary", False)
        ]
        if len(primary_contacts) != 1:
            raise ValidationError("Debe existir exactamente un contacto principal activo.")


CustomerContactFormSet = inlineformset_factory(
    Customer,
    CustomerContact,
    form=CustomerContactForm,
    formset=BaseCustomerContactFormSet,
    extra=1,
    can_delete=False,
)

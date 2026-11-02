from django import forms
from django.contrib.auth import get_user_model

from .models import AuditEvent


class AuditEventFilterForm(forms.Form):
    action = forms.ChoiceField(label="Acción", required=False)
    entity_type = forms.ChoiceField(label="Entidad", required=False)
    actor = forms.ModelChoiceField(
        label="Usuario",
        queryset=get_user_model().objects.none(),
        required=False,
    )
    date_from = forms.DateField(
        label="Desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        label="Hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        action_choices = AuditEvent.objects.order_by("action").values_list(
            "action", flat=True
        ).distinct()
        entity_choices = AuditEvent.objects.order_by("entity_type").values_list(
            "entity_type", flat=True
        ).distinct()
        self.fields["action"].choices = (
            ("", "Todas"), *((value, value) for value in action_choices)
        )
        self.fields["entity_type"].choices = (
            ("", "Todas"),
            *((value, value) for value in entity_choices),
        )
        self.fields["actor"].queryset = (
            get_user_model()
            .objects.filter(audit_events__isnull=False)
            .distinct()
            .order_by("username")
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_to < date_from:
            self.add_error("date_to", "La fecha final no puede ser anterior a la inicial.")
        return cleaned_data

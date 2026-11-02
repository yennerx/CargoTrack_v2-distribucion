from django import forms
from django.contrib.auth import get_user_model

from apps.catalogs.models import CatalogEntry, CatalogType

from .models import Incident, IncidentStatus


class IncidentForm(forms.ModelForm):
    class Meta:
        model = Incident
        fields = ("incident_type", "priority", "title", "description", "assigned_to")
        labels = {
            "incident_type": "Tipo de incidencia",
            "priority": "Prioridad",
            "title": "Título",
            "description": "Descripción",
            "assigned_to": "Responsable",
        }
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["incident_type"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.INCIDENT_TYPE, is_active=True
        )
        self.fields["priority"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.INCIDENT_PRIORITY, is_active=True
        )
        self.fields["assigned_to"].queryset = (
            get_user_model().objects.filter(is_active=True).order_by("username")
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"


class IncidentTransitionForm(forms.Form):
    status = forms.ChoiceField(choices=IncidentStatus.choices, label="Nuevo estado")
    observation = forms.CharField(label="Observación", widget=forms.Textarea(attrs={"rows": 3}))
    resolution = forms.CharField(
        label="Resolución", required=False, widget=forms.Textarea(attrs={"rows": 3})
    )

    def __init__(self, *args, allowed_statuses=None, **kwargs):
        super().__init__(*args, **kwargs)
        if allowed_statuses is not None:
            self.fields["status"].choices = [
                choice for choice in IncidentStatus.choices if choice[0] in allowed_statuses
            ]
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        resolution = cleaned_data.get("resolution", "").strip()
        if status in (IncidentStatus.RESOLVED, IncidentStatus.CLOSED) and not resolution:
            self.add_error("resolution", "La resolución es obligatoria para este estado.")
        return cleaned_data

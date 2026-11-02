from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group

from apps.carriers.models import CarrierType
from apps.catalogs.models import CatalogEntry, CatalogType
from apps.core.access_scope import scope_incidents
from apps.incidents.models import Incident, IncidentStatus

ADMIN_REPORTS = (
    ("users", "Usuarios"),
    ("customers", "Clientes"),
    ("carriers", "Transportistas"),
    ("incidents", "Incidencias"),
)

ADMIN_REPORT_PERMISSIONS = {
    "users": "auth.view_user",
    "customers": "customers.view_customer",
    "carriers": "carriers.view_carrier",
    "incidents": "incidents.view_incident",
}


class AdministrativeReportFilterForm(forms.Form):
    date_from = forms.DateField(
        label="Creado desde", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date_to = forms.DateField(
        label="Creado hasta", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    query = forms.CharField(label="Buscar", max_length=100, required=False)
    is_active = forms.ChoiceField(
        label="Estado",
        choices=(("", "Todos"), ("active", "Habilitado"), ("inactive", "Deshabilitado")),
        required=False,
    )
    group = forms.ModelChoiceField(label="Rol", queryset=Group.objects.none(), required=False)
    carrier_type = forms.ChoiceField(
        label="Tipo de transportista",
        choices=(("", "Todos"), *CarrierType.choices),
        required=False,
    )
    is_validated = forms.ChoiceField(
        label="Validación",
        choices=(("", "Todos"), ("yes", "Validado"), ("no", "No validado")),
        required=False,
    )
    incident_status = forms.ChoiceField(
        label="Estado de incidencia",
        choices=(("", "Todos"), *IncidentStatus.choices),
        required=False,
    )
    priority = forms.ModelChoiceField(
        label="Prioridad / criticidad", queryset=CatalogEntry.objects.none(), required=False
    )
    incident_type = forms.ModelChoiceField(
        label="Tipo de incidencia", queryset=CatalogEntry.objects.none(), required=False
    )
    assigned_to = forms.ModelChoiceField(
        label="Responsable", queryset=get_user_model().objects.none(), required=False
    )

    REPORT_FIELDS = {
        "users": {"date_from", "date_to", "query", "is_active", "group"},
        "customers": {"date_from", "date_to", "query", "is_active"},
        "carriers": {
            "date_from",
            "date_to",
            "query",
            "is_active",
            "carrier_type",
            "is_validated",
        },
        "incidents": {
            "date_from",
            "date_to",
            "query",
            "incident_status",
            "priority",
            "incident_type",
            "assigned_to",
        },
    }

    def __init__(self, *args, report_type, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        allowed_fields = self.REPORT_FIELDS[report_type]
        for field_name in set(self.fields) - allowed_fields:
            self.fields.pop(field_name)
        if "group" in self.fields:
            self.fields["group"].queryset = Group.objects.order_by("name")
        if "priority" in self.fields:
            self.fields["priority"].queryset = CatalogEntry.objects.filter(
                catalog_type=CatalogType.INCIDENT_PRIORITY
            )
        if "incident_type" in self.fields:
            self.fields["incident_type"].queryset = CatalogEntry.objects.filter(
                catalog_type=CatalogType.INCIDENT_TYPE
            )
        if "assigned_to" in self.fields:
            users = get_user_model().objects.order_by("username")
            if user is not None:
                visible_incidents = scope_incidents(Incident.objects.all(), user)
                users = users.filter(assigned_incidents__in=visible_incidents).distinct()
            self.fields["assigned_to"].queryset = users
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get("date_from")
        date_to = cleaned_data.get("date_to")
        if date_from and date_to and date_to < date_from:
            self.add_error("date_to", "La fecha final no puede ser anterior a la inicial.")
        return cleaned_data

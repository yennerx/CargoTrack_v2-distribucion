from django import forms

from apps.catalogs.models import CatalogEntry, CatalogType

from .models import DocumentVersion
from .validators import validate_document_file


class DocumentUploadForm(forms.Form):
    document_type = forms.ModelChoiceField(
        queryset=CatalogEntry.objects.none(), label="Tipo de documento"
    )
    stage = forms.ModelChoiceField(
        queryset=CatalogEntry.objects.none(), label="Etapa o estado", required=False
    )
    related_event = forms.CharField(label="Evento relacionado", required=False, max_length=150)
    file = forms.FileField(label="Archivo")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["document_type"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.DOCUMENT_TYPE, is_active=True
        )
        self.fields["stage"].queryset = CatalogEntry.objects.filter(
            catalog_type=CatalogType.ORDER_STATUS, is_active=True
        )
        for field in self.fields.values():
            field.widget.attrs["class"] = "form-control"

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        validate_document_file(uploaded_file)
        return uploaded_file


class VersionUploadForm(forms.Form):
    file = forms.FileField(label="Nueva versión")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["file"].widget.attrs["class"] = "form-control"

    def clean_file(self):
        uploaded_file = self.cleaned_data["file"]
        validate_document_file(uploaded_file)
        return uploaded_file


class DocumentVersionAdminForm(forms.ModelForm):
    class Meta:
        model = DocumentVersion
        fields = ("file",)

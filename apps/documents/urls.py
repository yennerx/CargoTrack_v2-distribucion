from django.urls import path

from . import views

app_name = "documents"

urlpatterns = [
    path("orden/<int:pk>/subir/", views.order_document_upload, name="order_upload"),
    path("transportista/<int:pk>/subir/", views.carrier_document_upload, name="carrier_upload"),
    path("<int:pk>/", views.document_detail, name="detail"),
    path("<int:pk>/version/", views.version_upload, name="version_upload"),
    path("version/<int:pk>/descargar/", views.version_download, name="download"),
    path("version/<int:pk>/restaurar/", views.version_restore, name="restore"),
    path("version/<int:pk>/eliminar/", views.version_delete, name="delete"),
]
